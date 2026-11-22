Codex `gpt-6.2-astra` at low reasoning effort, 2026-11-22, the cross-check the author asked for after each step. Verbatim. Tag A37 in the
review log. Its range is `55c6f6d..b414387`, run non-interactively (standard input closed) in its own worktree (`bella-r37`) at `b414387`: the
tee data link without a finaliser, the fixes of review A36 (RL-803 to RL-840) and the order of a display's stores (RL-825). Its probes
(`r37-probes/codex/`) stayed in that worktree. 18 findings; each was run on both sides by the session before any verdict (review log, A37).

---

# A37 conformance review at b414387

3,190 process pairs, 30 builds, 18 findings. Each numbered reproducer was run separately in `reduced/01` through `reduced/14` or `verify/15` through `verify/18`. Repeated evidence for a finding counts once in the finding total.

All row paths below are relative to `r37-probes/codex`. For a row `suite/row`, run `PYTHONHASHSEED=0 .venv/bin/python r37-probes/codex/suite/prog.py row`, then run the binary printed by `./r37-build r37-probes/codex/suite/prog.py` with the same row argument and seed. Each row directory contains both byte streams and statuses. Runs used a 120-second timeout and an 8000000 KiB virtual-memory limit.

## A37-01 · High · A foreign built-in allocator changes whether construction succeeds

`runtime/src/types.cpp:649 (type_call), :34 and :74 (wrapper safety check)`. Reproducer from `alloc/object-builtin-empty`:

```python
class B: pass
class C(B): pass
C.__new__ = list.__new__
try: print(type(C()).__name__)
except TypeError: print("TypeError")
```

CPython prints `C`. Bella prints `TypeError`. Stderr is empty and both exit 0. Explicit `object.__new__(C)` gives the same split (row `object-builtin-obj`), and the reduction row fails already while obtaining its receiver. CPython's update_one_slot preserves the inherited allocator when it sees a tp_new_wrapper. Although Bella records that history, the construction and wrapper safety checks still consult the visible allocator name.


The affected allocator matrix rows are listed below. Each row name is `alloc/BASE-builtin-OP`. Bella prints TypeError throughout. Both processes exit 0 with empty stderr.

| OP | CPython stdout | BASE |
|---|---|---|
| arg | AttributeError | BufferedRandom, BufferedReader, BufferedWriter, TextIOWrapper |
| arg | C | Exception, FileIO, OSError, bytes, int, str |
| copy | C | Exception, OSError, OrderedDict, defaultdict, deque, frozenset, set |
| empty | C | BufferedIOBase, BytesIO, Exception, IOBase, OSError, OrderedDict, RawIOBase, StringIO, TextIOBase, bytes, defaultdict, deque, dict, frozenset, int, object, set, str, tuple |
| init | NoneType | bytes, frozenset, int, str, tuple |
| kw | C | OrderedDict, defaultdict, dict |
| obj | C | BufferedIOBase, BufferedRWPair, BufferedRandom, BufferedReader, BufferedWriter, IOBase, RawIOBase, TextIOBase, TextIOWrapper, object |
| objarg | C | BufferedRWPair, BufferedRandom, BufferedReader, BufferedWriter, TextIOWrapper |
| reduce | tuple | BufferedIOBase, BytesIO, Exception, IOBase, OSError, OrderedDict, RawIOBase, StringIO, TextIOBase, bytes, defaultdict, deque, dict, frozenset, int, object, set, str, tuple |

The same dispatch error appears with int.__new__ set through a metaclass in `history/meta` (CPython: set __new__, C, C. Bella: set __new__, TypeError, C) and through type.__setattr__ in `special/other-construct` (Child versus TypeError).

## A37-02 · Medium · Tuple and float subclass initializers cannot accept their own keywords

`runtime/src/types.cpp:1070`. Row `alloc/tuple-init-kw` reduces to:

```python
class C(tuple): pass
C.__init__ = lambda self, **kw: None
try: print(type(C(k=1)).__name__)
except TypeError: print("TypeError")
```

CPython prints `C`. Bella prints `TypeError`. Both exit 0 with empty stderr. CPython's generated tuple_new in Objects/clinic/tupleobject.c.h:96 checks for keywords only when the type is tuple or inherits its initializer slot. Bella's tuple allocator checks the argument list even when the subclass handles keywords itself.

The same missing initializer-slot test as A37-02 affects float at `runtime/src/float.cpp:224`. In `history/tuple` and `history/float`, CPython prints TypeError, TypeError, Y on separate lines. Bella prints TypeError three times. The shared row first assigns the inherited initializer, deletes it, then installs a Python initializer accepting keywords. Empty stderr and status 0 throughout.

## A37-03 · Medium · A dict subclass loses its sequence-length slot

`runtime/src/ops.cpp:368`. Row `protocol/ast-dictsub`:

```python
import ast
class D(dict): pass
class A(ast.AST): _fields = D(x=1)
try: print(repr(A()))
except Exception as e: print(type(e).__name__)
```

CPython prints `KeyError`. Bella prints `TypeError`. Both exit 0 with empty stderr. CPython gets length 1 and proceeds to look up field 0. Bella's _sequence_size walks to the class that supplied __len__ and rejects dict there. A Python subclass of dict can have sq_length even when dict itself has only mp_length.

## A37-04 · Medium · Re-entering islice from a skipped item's finaliser changes the outer exception

`runtime/prelude/itertools.py:715`. Row `cleanup/slice-again`. The relevant program is:

```python
from itertools import islice
class V:
    def __del__(self):
        try: next(w)
        except GeneratorExit: pass
def source():
    yield V()
    raise GeneratorExit
it = source()
w = islice(it, 1, 2)
try: next(w)
except BaseException as e: print(type(e).__name__)
```

The saved row also instruments the finalisers and the outer handler. Its complete CPython stdout is:

```text
item LookupError
again GeneratorExit
input LookupError
caught StopIteration
end
```

Bella prints the same lines with `caught TypeError` on line four. Empty stderr, status 0 on both. CPython's islice_next takes the iterator and its next function at entry. In Bella, the inner call clears self._it on GeneratorExit. The resumed outer call reads that field again and calls next(None).

## A37-05 · Medium · reversed and filter accept a keyword on subclasses that inherit their initializer

`runtime/prelude/iterating.py:148`. Row `history/reverse` reduces to:

```python
class C(reversed): pass
try: print(type(C([], k=1)).__name__)
except TypeError: print("TypeError")
```

The row exercises three initializer histories. CPython prints TypeError, TypeError, list_reverseiterator on separate lines. Bella prints list_reverseiterator three times. Both exit 0 with empty stderr. The prelude checks only whether cls is reversed. The generated CPython wrapper also checks whether the initializer slot is the base slot. The list's reverse iterator is returned before a subclass initializer could reject the unexpected keyword.

A37-05 also applies to filter at `runtime/prelude/iterating.py:454`. In `clinic/filter-same` (explicitly assigning the inherited initializer), CPython prints TypeError and Bella prints C. The two meta rows for filter and reversed prepend one `lookup` on both sides and show the same keyword admission error. All exit 0 with empty stderr.

## A37-06 · Medium · BufferedRWPair refuses a keyword a subclass allocator accepts

`runtime/prelude/_io.py:2112`. Row `streams/BufferedRWPair-clinic-release`:

```python
import io
class C(io.BufferedRWPair):
    def __new__(cls,*a,**kw): return object.__new__(cls)
b = io.BytesIO()
try: print(type(C(b,b,k=1)).__name__)
except TypeError: print("TypeError")
```

The row uses a BytesIO whose close prints `close`. CPython stdout is `close\nC\n`. Bella stdout is `TypeError\nclose\n`. Both exit 0 with empty stderr. Modules/_io/clinic/bufferedio.c.h:1158 applies _PyArg_NoKeywords only if the object's allocator equals the base allocator or its type is exact. The prelude tests kwds unconditionally.

## A37-07 · Medium · A sequence released by reversed sees the wrong handled exception

`runtime/prelude/iterating.py:175`. Rows `pending/index` and `pending/type`:

```python
import sys
class Seq:
    def __len__(self): return 1
    __getitem__ = staticmethod([].__getitem__)
    def __del__(self): print('seq',type(sys.exception()).__name__)
try: raise LookupError()
except LookupError:
    w = reversed(Seq())
    try: next(w)
    except BaseException as e: print('caught',type(e).__name__)
```

| Row | CPython stdout | Bella stdout |
|---|---|---|
| index | `seq LookupError\ncaught StopIteration\n` | `seq IndexError\ncaught StopIteration\n` |
| type (use dict.__getitem__ as the method) | `seq LookupError\ncaught TypeError\n` | `seq TypeError\ncaught TypeError\n` |

Empty stderr and status 0 on both sides. CPython's reversed_next clears IndexError before Py_CLEAR(ro->seq), or leaves the other error pending. The seq finaliser sees the enclosing LookupError either way. Bella clears self._seq inside its active except handler.

## A37-08 · Medium · An ordinary built-in callable assigned to __new__ leaves the wrong allocator state

`runtime/src/types.cpp:410`. Rows `special/{len,bound}-{init,deleted}`:

```python
class Base: pass
class Child(Base): pass
c = Child()
Base.__new__ = len
try: print(type(object.__init__(c,1)).__name__)
except TypeError: print("TypeError")
```

CPython prints NoneType and Bella prints TypeError in all four rows, with empty stderr and status 0. The bound variant stores [].append. The deleted variants remove the attribute before the final call. Bella's new_is_a_wrapper treats every Kind::Builtin as an allocator wrapper. CPython's update_one_slot singles out built-ins whose C function is tp_new_wrapper. An ordinary built-in switches the class and its inheriting children to slot_tp_new, which changes the excess-argument check in object.__init__ even after deletion.

## A37-09 · Medium · itertools allocator validation invokes a metaclass descriptor

`runtime/prelude/itertools.py:68`. Rows `clinic/{chain,cycle,dropwhile,filterfalse,islice,pairwise,starmap,takewhile}-meta`:

```python
from itertools import pairwise
class Meta(type):
    @property
    def __init__(cls):
        print('lookup')
        return object.__init__
class C(pairwise,metaclass=Meta): pass
try: C([], k=1)
except TypeError: print("TypeError")
```

CPython stdout is `lookup\nTypeError\n`. Bella stdout is `lookup\nlookup\nTypeError\n`. Both exit 0 with empty stderr. One lookup happens during class construction on both sides. _new_no_keywords compares cls.__init__ to own.__init__ using Python attribute access, invoking the metaclass a second time. CPython reads the tp_init function pointer.

In `verify/meta`, the descriptor raises OSError only after the class is ready. CPython prints TypeError and Bella prints OSError. Both exit 0 with empty stderr.

## A37-10 · Medium · IOBase.close calls the closed-flag setter while handling a flush error

`runtime/prelude/_io.py:440`. Rows `handlers/flush` and `handlers/setter`:

```python
import io, sys
class F(io.IOBase):
    def flush(self): raise ValueError()
    def __setattr__(self,k,v):
        print('setter',type(sys.exception()).__name__)
        object.__setattr__(self,k,v)
try: raise LookupError()
except LookupError:
    try: F().close()
    except Exception as e: print(type(e).__name__,type(e.__context__).__name__)
```

CPython prints `setter LookupError\nValueError LookupError\n`. Bella prints `setter ValueError\nValueError LookupError\n`. When the setter itself raises TypeError after storing the flag, both sides print `TypeError ValueError` on line two, but retain their different first lines. Both rows exit 0 with empty stderr. CPython's _io__IOBase_close_impl takes the pending flush error off the thread before calling PyObject_SetAttr and chains the errors afterward. Bella calls setattr in finally.

## A37-11 · Medium · Eviction after a failed LRU cache store exposes the cache error to finalisers

`runtime/prelude/_functools.py:784`. Row `handlers/lru`. The reproducer uses two cache entries with colliding hashes. Comparing key 1 to key 2 raises on the third comparison, at the insertion that reuses the oldest link. The complete program for this row is:

```python
import sys, functools
def note(k): print(k,type(sys.exception()).__name__)
class K:
    def __init__(self,n): self.n=n
    def __hash__(self): return 0
    def __eq__(self,o):
        if self.n==1 and o.n==2:
            count.append(1)
            if len(count)==3: raise ValueError()
        return self.n==o.n
    def __del__(self): note('key'+str(self.n))
class R:
    def __init__(self,n): self.n=n
    def __del__(self): note('result'+str(self.n))
@functools.lru_cache(2)
def f(k): return R(k.n)
count=[]
try: raise LookupError()
except LookupError:
    try:
        for i in range(3): f(K(i))
    except BaseException as e: print(type(e).__name__,type(e.__context__).__name__)
f.cache_clear()
```

| CPython stdout | Bella stdout |
|---|---|
| result2 LookupError | result2 ValueError |
| key0 LookupError | key0 ValueError |
| result0 LookupError | result0 ValueError |
| ValueError LookupError | ValueError LookupError |
| key2 LookupError | key2 LookupError |
| key1 NoneType | key1 NoneType |
| result1 NoneType | result1 NoneType |

Both exit 0 with empty stderr. The failed insertion releases the new result, old key and old result in the correct order. Bella does all three deletes inside except BaseException. The C bounded_lru_cache_update_lock_held releases those objects with the comparison error pending.

## A37-12 · Medium · A failed AST field store hashes its field under a different exception state

`runtime/prelude/_ast.py:177`. Row `morepending/ast`:

```python
import sys, io, ast
def note(s): print(s,type(sys.exception()).__name__)
class Field:
    def __hash__(self):
        note('hash')
        return 1
class Node(ast.AST): _fields=(Field(),)
try: raise LookupError()
except LookupError:
    try:
        Node(1)
    except BaseException as e: print(type(e).__name__)
```

CPython stdout is `hash LookupError\nSystemError\n`. Bella stdout is `hash LookupError\nhash TypeError\nTypeError\n`. Both exit 0 with empty stderr. CPython's ast_type_init calls PySet_Discard immediately after the failed PyObject_SetAttr (Python/Python-ast.c:5320). A Python hash callback is entered with the C error still pending, and this callback produces SystemError. Bella invokes discard in a finally handler, where the setter error is handled and the hash callback completes.

## A37-13 · Medium · Closing a partially constructed BufferedRWPair reader exposes the writer error

`runtime/prelude/_io.py:2141`. Row `morepending/pair`:

```python
import sys, io, ast
def note(s): print(s,type(sys.exception()).__name__)
class Raw(io.BytesIO):
    def close(self):
        note('close')
        super().close()
class Writer(io.BytesIO):
    count=0
    def writable(self):
        self.count+=1
        if self.count==2: raise ValueError()
        return True
try: raise LookupError()
except LookupError:
    try:
        io.BufferedRWPair(Raw(),Writer())
    except BaseException as e: print(type(e).__name__)
```

CPython stdout is `close LookupError\nValueError\n`. Bella stdout is `close ValueError\nValueError\n`. Both exit 0 with empty stderr. The first writable check succeeds. The BufferedWriter constructor checks again and fails. CPython clears self->reader with the failure pending. Bella releases the newly built reader in finally, so its close callback sees the writer error.

## A37-14 · Medium · FileIO warning formatting runs under the failed flush handler

`runtime/prelude/_io.py:1106`. Row `morepending/file`:

```python
import sys, io, ast
def note(s): print(s,type(sys.exception()).__name__)
class F(io.FileIO):
    def flush(self): raise ValueError()
    def __repr__(self): note('repr');return 'F'
try: raise LookupError()
except LookupError:
    try:
        x=F('/dev/null','r')
        x._finalizing=True
        x.close()
    except BaseException as e: print(type(e).__name__)
```

CPython stdout is `repr LookupError\nValueError\n`. Bella stdout is `repr ValueError\nValueError\n`. Both exit 0 with empty stderr. FileIO.close catches the base close error and calls _fileio_dealloc_warn inside the handler. In fileio.c, _io_FileIO_close_impl saves the error with PyErr_GetRaisedException before formatting the ResourceWarning. The source object's repr observes the enclosing handler on CPython.

## A37-15 · Medium · bisect treats an exact frozendict as a sequence

`runtime/prelude/_bisect.py:40`. Row `capi/frozen`:

```python
import bisect
try: print(bisect.bisect(frozendict({0:1}),1))
except Exception as e: print(type(e).__name__)
```

CPython prints TypeError and Bella prints 1. Both exit 0 with empty stderr. The prelude maintains its own table of C types with mapping slots only. It omits frozendict, so both its size check and its indexed access accept this mapping.

## A37-16 · Medium · The JSON encoder calls a numeric multiply hook on a non-sequence indent

`runtime/prelude/_json.py:545`. Row `capi/indentmul`:

```python
import _json
class Mul:
    def __mul__(self,n): print('mul'); return ' '
enc=_json.make_encoder(None,None,_json.encode_basestring,Mul(),':',',',False,False,False)
try: print(enc(1,2))
except Exception as e: print(type(e).__name__)
```

CPython prints `TypeError\n` and Bella prints `mul\n('1',)\n`. Both exit 0 with empty stderr. For a nonzero starting indent level CPython calls PySequence_Repeat, whose fallback to numeric multiplication requires a sequence. Python multiplication invokes Mul.__mul__ without that condition.

## A37-17 · Medium · A mapping's method result survives iteration that CPython starts after releasing it

`runtime/prelude/_json.py:705`. Row `capi/items`:

```python
import _json
class Items:
    def __iter__(self): print('iter items'); return self
    def __next__(self): print('next items'); raise StopIteration()
class Product:
    def __iter__(self): return Items()
    def __del__(self): print('drop items')
class D(dict):
    def items(self): return Product()
enc=_json.make_encoder(None,None,_json.encode_basestring,None,':',',',False,False,False)
print(enc(D(a=1),0))
```

CPython prints `drop items\niter items\nnext items\n('{}',)\n`. Bella prints `iter items\nnext items\ndrop items\n('{}',)\n`. Both exit 0 with empty stderr. Objects/abstract.c's method_output_as_list drops the method result once it has the iterator, before PySequence_List. The prelude keeps the original in its items variable until list(iter(items)) has finished.

The same ownership error occurs in `runtime/prelude/posix.py:748` for PyMapping_Keys and PyMapping_Values. The rows `methodlist/{items,keys,values}-{ok,err}` use a method result with a finaliser and a separate iterator. For all six, CPython prints `drop NAME`, `iter NAME`, `next NAME`. Bella prints `iter NAME`, `next NAME`, `drop NAME`. The final line agrees: `('{}',)` for items-ok, `FileNotFoundError NoneType` for keys-ok and values-ok, and `LookupError NoneType` for each err row. Both sides exit 0 with empty stderr. The posix rows pass the mapping as the environment to posix_spawn with a nonexistent executable.

## A37-18 · High · Reinitializing FileIO clears access-mode flags CPython preserves

`runtime/prelude/_io.py:841`. Row `invalidio/FileIO-prior-props`:

```python
import io
s=io.FileIO('/dev/null','rb')
try: s.__init__('/dev/null','qq')
except ValueError: pass
print(s.closed,s.mode)
```

The saved row prints the setup error and properties individually. CPython prints `setup ValueError\nclosed True\nname /dev/null\nmode rb\nraw AttributeError\nencoding AttributeError\nerrors AttributeError\nnewlines AttributeError\n`. Bella changes `mode rb` to `mode wb`. Empty stderr, status 0. In CPython fileio_new zeroes the access flags on allocation. The initialization loop sets individual flags as mode characters are recognized. The prelude clears all five flags before it examines the first character of each new mode.

The successful reopening row `rawmode/a-r` shows a change a caller can act on immediately. It opens /dev/null in append mode, calls __init__ again in read mode, and exercises both access directions.

| CPython stdout | Bella stdout |
|---|---|
| `mode ab+` | `mode rb` |
| `readable True` | `readable True` |
| `writable True` | `writable False` |
| `read b''` | `read b''` |
| `write 1` | `write UnsupportedOperation` |

Both exit 0 with empty stderr. Additional differing rawmode rows: a-q, a-rx, a-w, r+-a, r+-q, r+-r, r+-rx, r+-w, r-a, r-q, r-w, w-r, w-rx.

## Scope and coverage

The Python and C sources distinguish three cleanup paths that look alike in a prelude. A pending C error can coexist with the caller's handled exception. CPython sometimes takes the pending error off the thread before a callback (IOBase.close, FileIO.close, TextIOWrapper.tell and the error label of _io.open). Other paths release references directly with an error pending (islice, reversed, the bounded LRU update, BufferedRWPair construction and AST positional-field initialization). A third group resets native bookkeeping, including the buffered stream's owner flag, repr guards, and the regular-expression scanner's executing flag. Changing such a flag does not itself invoke a Python finaliser.

Additional pending-error cleanup sites identified in the preludes include batched.__next__ (clear input and partial batch), odict_iterator.__next__ and _odictiter_nextkey (release key/current position), _od_add_pairs (release the pair and iterator), BufferedRWPair.close and the buffered and text close paths (try the second close after the first failure), and Context.run (restore the previous context after the callback). The batched error and incomplete-batch probes matched. The traceback and finaliser probes directly established the numbered findings above. A source-only site is not counted as a finding.

For the allocator tests, the pinned Argument Clinic headers use the **allocator slot** to decide whether list.__init__, _random.Random.__init__ and _io.BufferedRWPair.__init__ reject keywords. The complementary **initializer-slot** check applies to tuple, float, reversed, method, instancemethod, code, _collections._tuplegetter and the generated itertools wrappers for pairwise, _grouper, _tee_dataobject, _tee, cycle, dropwhile, takewhile, starmap and filterfalse. Handwritten checks also occur in filter, frozenset, islice and chain. Several of those C types prohibit subclassing. This inventory distinguishes the two checks; the process comparisons cover the subclassable constructors named in the findings and suites.

Bella ended by name for sys._getframe(1) and generator.gi_frame, including access from a package member. This prevented observing another frame's live locals through those routes. Direct release-order and handled-exception observations ran separately. The __bases__ replacement and instance __class__ assignment rows also stopped by name. Four temporary-argument lifetime rows in params fall under RL-695. A shutdown-only difference in reentry/pair-bad was excluded. With explicit release before program exit (verify/release), the finalisation order agreed. The I/O and consumer matrices are sampled across states and callbacks; they do not establish every combination of callbacks, methods and class histories.

## What matched

3,002 rows matched stdout, stderr and exit status byte for byte. 27 additional rows ended at a named stop. The tables and saved outputs include repeated confirmations and the explicitly excluded cases.

| Probe | Agreement observed |
|---|---|
| order, edges, temporaries, frames, package | Every row matched. This includes augmented and walrus assignment, imports, with and for targets, except cleanup, definitions and defaults, prior annotations, private names, conditional displays, nested and package-member functions, mixed global/nonlocal stores, and frame teardown with several cells on return, exception, generator close, exhaustion or drop. |
| consume | All 54 rows matched, including the StopIteration payload, exception class, context, cause, suppression flag and traceback lines. |
| cleanup, reentry | The finalisers' handled exceptions, unraisable hook and generator-close observations matched in 49 rows. The islice difference and excluded shutdown row are described above. |
| mapping, extra | All 105 rows matched. Coverage includes mutable keys lists, non-list key collections, malformed iterators, keyword expansion, subclass copying, exact and subclassed pairs, conversion notes and re-entry while pairwise recycles a pair. |
| io, streams, invalidio | All 273 TextIOWrapper state/method rows matched. The other suites contributed 239 matches, including encoder and decoder factory errors, a non-text codec, failed initialization on new and previously usable streams, detached streams and streams closed underneath a wrapper. The finalisation probe in verify also matched flush, close, bytes written and recorded warnings. |
| protocol, capi | 87 of the 88 protocol rows matched, including operator searches, containment, concatenation, indexed access, repetition and length hints over the selected types. Numeric index failure and int-subclass conversion warnings were compared on stderr. The bisect mappingproxy and dict-subclass controls agreed. |
| links | All ten rows matched: direct data-link construction around the 57-item boundary, tee nesting and copying, resumption after an iterator error, re-entry at a link boundary, Context copies, snapshot iterators, equality and token reset. |
| alloc | 2,027 of 2,106 rows matched across 26 base types, nine allocator histories and nine operations, including direct and indirect construction, initialization, copying and reduction. |
