Codex `gpt-6.2-astra` at low reasoning effort, 2026-11-22, the cross-check the author asked for after each step. Verbatim. Tag A35 in the
review log. Its range is `9966dbe..d558f52`, run non-interactively (standard input closed) in its own worktree (`bella-r35`) at `d558f52`: the
state an allocator leaves (`__alloc__`) and the fixes of review A34 (RL-754 to RL-776). Its probes (`r35-probes/codex/`) stayed in that
worktree. 25 findings; each was run on both sides by the session before any verdict (review log, A35).

---

# A35 conformance review · 9966dbe..d558f52

**25 confirmed findings.** A35-06 changes computed results: the same iterator sums to 2 in CPython and 3 in Bella. A35-22 changes which OSError subclass a caller catches. The CSV allocator and buffered-stream findings expose objects or stream state that CPython does not produce. The findings describe the reviewed checkout; the comparisons establish behavior at the tip, without attributing every defect to a commit in the range.

All paths are relative to the detached checkout. Each row runs in a fresh process. For a probe directory `d` and the row named in a finding, the invocations were:

```bash
ulimit -v 8000000
export PYTHONHASHSEED=0
timeout 600 ./r35-build "$d/prog.py" > "$d/build.out"
timeout 120 .venv/bin/python "$d/prog.py" "$row"
timeout 120 "$(tail -1 "$d/build.out")" "$row"
```

The directories under `r35-probes/codex/` contain the programs and the individual stdout, stderr and status files. Unless indicated otherwise, both processes exited 0 with empty stderr. Each displayed output line ends with a newline.

## A35-01 · Medium · Annotation descriptors consult the wrapper subclass's dictionary property

`runtime/prelude/builtins.py:484` and `:493`. Rows `members/{sread,swrite,cread,cwrite}`. Minimal read case:

```python
def f(): pass
class S(staticmethod):
    @property
    def __dict__(self):
        print("dict lookup")
        raise LookupError
x = S(f)
try: print(x.__annotations__)
except LookupError: print("LookupError")
```

CPython prints `{}`. Bella prints `dict lookup` then `LookupError`. Substituting classmethod gives the same difference. The write rows first assign `x.__annotations__ = {"v": 1}` and then print it. CPython prints `{'v': 1}`. Bella prints the same two failure lines as on read. Both descriptor helpers evaluate `obj.__dict__`. CPython's `Objects/funcobject.c:1414` and its matching setter call `PyObject_GenericGetDict`, bypassing the property.

## A35-02 · Medium · Reducing a partial can raise while retrieving its instance state

`runtime/prelude/_functools.py:330`. Row `members/partial`.

```python
from functools import partial
class P(partial):
    @property
    def __dict__(self):
        print("dict lookup")
        raise LookupError
p = P(int)
p.extra = 3
try: print(p.__reduce__()[2][3])
except LookupError: print("LookupError")
```

CPython prints `{'extra': 3}`. Bella prints `dict lookup` then `LookupError`. Setting an instance attribute first matters because Bella tests whether a dictionary exists before reading `self.__dict__`. CPython's `Modules/_functoolsmodule.c:792` reads the partial object's dictionary pointer directly.

The inverse operation also dispatches to the subclass. Row `construction/restore` uses this program:

```python
from functools import partial
class P(partial):
    @property
    def __dict__(self): return {}
    @__dict__.setter
    def __dict__(self, value): print("dict setter"); raise LookupError
p = P(int)
try:
    p.__setstate__((int, (), {}, {"v": 2}))
    print(p.v)
except LookupError: print("LookupError")
```

CPython prints `2`. Bella prints `dict setter` then `LookupError`. The store at `runtime/prelude/_functools.py:361` reaches the dictionary descriptor, whereas partial_setstate replaces the dictionary pointer.

## A35-03 · High · A delegated iterator's StopIteration can change the value of a yield-from expression

`runtime/src/generator.cpp:445` and `:394`. Rows `exception/next` and `exception/throw`.

```python
class Stop(StopIteration):
    @property
    def value(self):
        print("value lookup")
        return 99
class I:
    def __iter__(self): return self
    def __next__(self): raise Stop(7)
def gen(): print("returned", (yield from I()))
try: next(gen())
except StopIteration: print("StopIteration")
```

CPython prints `returned 7` then `StopIteration`. Bella prints `value lookup`, `returned 99`, then `StopIteration`. The second row suspends the outer generator first and raises the same exception from the delegate's `throw` method. Its outputs are identical to the first row's. Both Bella paths evaluate the exception's public `value` attribute. CPython reads the StopIteration object's stored value in `Objects/genobject.c:811`.

## A35-04 · Medium · An unrelated metaclass descriptor can prevent object reduction

`runtime/prelude/bootstrap.py:2161`. Row `exception/state`.

```python
import copyreg
class M(type):
    @property
    def __getstate__(cls):
        print("meta state")
        raise LookupError
class X(metaclass=M): pass
x = X()
x.a = 3
try: print(x.__reduce_ex__(4)[2])
except LookupError: print("LookupError")
```

CPython prints `{'a': 3}`. Bella prints `meta state` then `LookupError`. Bella obtains the instance's bound method and then evaluates `type(obj).__getstate__` to identify the default implementation. CPython's `object_getstate` in `Objects/typeobject.c` identifies the bound built-in by its C function pointer.

## A35-05 · Medium · GenericAlias formatting and parameter substitution run tuple subclass overrides

`runtime/prelude/bootstrap.py:698`, `:708`, `:751`, `:754`, `:866`. Rows in `generics`. The reproducer uses these shared declarations and one expression from the table, evaluated as `try: print(expression)` with `except BaseException as e: print(type(e).__name__)`.

```python
from types import GenericAlias
from typing import TypeVar
T = TypeVar("T")
class Tup(tuple):
    def __iter__(self): print("iter"); raise LookupError
    def __len__(self): print("len"); raise ValueError
class Has: __parameters__ = Tup((T,))
class Unpack: __typing_unpacked_tuple_args__ = Tup((int,))
```

| Row | Expression | CPython stdout, in order | Bella stdout, in order |
|---|---|---|---|
| pars | `GenericAlias(list,Tup((T,))).__parameters__` | `(~T,)` | `iter`, `LookupError` |
| subpars | `list[Has()].__parameters__` | `(~T,)` | `iter`, `LookupError` |
| repr | `repr(GenericAlias(list,Tup((int,))))` | `list[int]` | `iter`, `LookupError` |
| sub | `list[T][Tup((int,))]` | `list[int]` | `iter`, `LookupError` |
| unpack | `list[T][Unpack()]` | `iter`, `LookupError` | `len`, `ValueError` |

`Objects/genericaliasobject.c` uses tuple size and item macros in `ga_repr`, `_Py_make_parameters`, and `_unpack_args`. Bella uses ordinary iteration, conversion to tuple, and truth testing. The last row distinguishes two stages: CPython inspects the last tuple cell directly, then reaches the iterator during slice insertion. Bella's truth test raises before insertion.

## A35-06 · High · Consuming a Python iterator keeps its last yielded item alive across the next call

`runtime/prelude/_collections.py:103`, `_functools.py:84`, `iterating.py:69`, `_csv.py:51`, `_io.py:86`. Rows in `lifetime`. Minimal deque case:

```python
from collections import deque
class N(int):
    def __del__(self): print("drop", int(self))
class I:
    i = 0
    def __iter__(self): return self
    def __next__(self):
        self.i += 1
        print("next", self.i)
        if self.i > 2: raise StopIteration
        return N(self.i)
    def __del__(self): print("drop iterator")
class S:
    def __iter__(self): return I()
deque(S(), maxlen=0)
print("after")
```

The generator introduced by RL-765 suspends at `yield item` with a local reference to the item. It requests the next value before replacing that local. In particular, the deque's zero-capacity loop explicitly deletes its item, but that cannot release the generator's reference. CPython's `consume_iterator` in `Modules/_collectionsmodule.c` decrements the item before calling the iterator again. A finalizer can therefore change the input to the *next* call in CPython while Bella is still holding the previous object. The table gives both complete event sequences. Each space-separated symbol denotes a line: N1–N3 are `next 1` through `next 3`, D1/D2 are `drop 1`/`drop 2`, B is `drop b'x'`, I is `drop iterator`, A is `after`.

| Rows | CPython | Bella |
|---|---|---|
| deque, left | N1 D1 N2 D2 N3 I A | N1 N2 D1 N3 D2 I A |
| sum, float, complex, csv | N1 D1 N2 D2 N3 I A | N1 N2 D1 N3 I D2 A |
| buf, lines | N1 B N2 B N3 I A | N1 N2 B N3 I B A |
| min | N1 N2 D2 N3 I D1 A | N1 N2 N3 I D2 D1 A |
| reduce | N1 N2 D1 N3 D2 I A | N1 N2 D1 N3 I D2 A |

The io rows yield bytes subclasses. Reduce uses an initial zero and a callback returning zero. The max control, which keeps the second item as its result, agreed.

The `feedback` probe makes the different lifetime change the data itself. Minimal `feedback/sum` case:

```python
alive = 0
class Item(int):
    def __new__(cls, n):
        global alive
        alive += 1
        return super().__new__(cls, n)
    def __del__(self):
        global alive
        alive -= 1
class I:
    n = 0
    def __iter__(self): return self
    def __next__(self):
        self.n += 1
        if self.n > 2: raise StopIteration
        return Item(1 + alive)
print(sum(I()))
```

| Row in feedback | CPython stdout lines | Bella stdout lines |
|---|---|---|
| sum, list (a list subclass returning I from __iter__) | `2` | `3` |
| float | `2.0` | `3.0` |
| complex | `(2+0j)` | `(3+0j)` |
| generic (accumulator logs each operand) | `arg 1`, `arg 1` | `arg 1`, `arg 2` |
| count (_count_elements with a mapping that retains no keys) | `key 1`, `key 1` | `key 1`, `key 2` |

## A35-07 · Medium · Pattern matching reads type flags through a metaclass property

`runtime/prelude/match.py:42`, `:47`, `:116`. Rows `patterns/{seq,map,self}`.

```python
class M(type):
    @property
    def __flags__(cls):
        print("flags lookup")
        raise LookupError
class L(list, metaclass=M): pass
try:
    match L([1]):
        case [x]: print(x)
except LookupError: print("LookupError")
```

CPython prints `1`. Changing the pattern to `case L(x)` prints `[1]`. The mapping row uses a dict subclass with the same metaclass, subject `D(k=2)`, and pattern `{"k": x}`. It prints `2`. Bella prints `flags lookup` then `LookupError` on all three. The MATCH_SEQUENCE and MATCH_MAPPING instructions in `Python/bytecodes.c` and the match-self test in `_PyEval_MatchClass` use the type's stored flags.

## A35-08 · Medium · Class building and class patterns invoke metaclass equality during type checks

`runtime/prelude/build_class.py:34`, `:39`, and `runtime/prelude/match.py:98`. Rows `factory/{derive,match}` and `patterns/eq`. Minimal setup for the first two:

```python
active = False
class MM(type):
    def __eq__(cls, other):
        if active:
            print("meta eq")
            raise ArithmeticError
        return cls is other
    __hash__ = type.__hash__
class M(type, metaclass=MM): pass
class X(metaclass=M): pass
active = True
```

In a try block, run `class Y(X): pass` followed by `print("created")`, or run `match X():` with `case X(): print("matched")`. Catch ArithmeticError and print its class name. CPython prints `created` and `matched` respectively. Bella prints `meta eq` then `ArithmeticError` for each. With equality active from the outset, Bella already raises at the declaration of X (`patterns/eq`). Membership in the MRO tuple uses rich equality for nonidentical entries. CPython's type and subtype checks compare type pointers.

## A35-09 · High · A metaclass equality method can prevent stream finalization

`runtime/prelude/_io.py:441`. Row `identity/final`.

```python
import io, sys
class M(type):
    def __eq__(cls, other):
        print("compare class")
        raise LookupError
    __hash__ = type.__hash__
class R(io.BytesIO, metaclass=M):
    def close(self): print("close")
sys.unraisablehook = lambda e: print("unraisable", e.exc_type.__name__)
r = R()
del r
```

CPython prints `close`. Bella prints `compare class` then `unraisable LookupError`. Its finalizer uses tuple membership to recognize three exact built-in classes that skip finalization. Rich equality with a different class can run before Bella even inspects whether the stream is closed.

## A35-10 · Medium · Weak-reference operand checks invoke metaclass equality

`runtime/prelude/_weakref.py:149`, `:159`, `:408`. Rows `identity/{eq,ne,remove}`.

```python
import _weakref
class M(type):
    def __eq__(cls, other):
        print("compare class")
        raise LookupError
    __hash__ = type.__hash__
class X(metaclass=M): pass
x = X()
r = _weakref.ref(x)
try: print(r.__eq__(x))
except BaseException as e: print(type(e).__name__)
```

CPython prints `NotImplemented` for both `r.__eq__(x)` and `r.__ne__(x)`. Calling `_weakref._remove_dead_weakref({"k": x}, "k")` instead prints `TypeError` from the handler. Bella prints `compare class` then `LookupError` for all three. Each path uses membership in a tuple of proxy types. The corresponding `PyWeakref_Check` uses exact type checks for the proxies.

## A35-11 · Medium · Removing a dead weak reference hashes the key up to three times

`runtime/prelude/_weakref.py:403`–`411`. Rows `identity/{hashdead,hashmiss}`.

```python
import _weakref
class K:
    active = False
    def __hash__(self):
        if self.active: print("hash")
        return 1
class X: pass
k, x = K(), X()
d = {k: _weakref.ref(x)}
del x
k.active = True
_weakref._remove_dead_weakref(d, k)
print(len(d))
```

CPython prints `hash` then `0`. Bella prints `hash` three times then `0`. Clearing the dictionary before enabling logging gives one hash in CPython and two in Bella, followed by `0` on both. The prelude calls `hash(key)`, looks up the key, and on deletion looks it up again. CPython's `_PyDict_DelItemIf` computes the hash once and conditionally removes the entry it found.

## A35-12 · High · Subclasses of the CSV reader and writer can be instantiated without runtime state

`runtime/src/types.cpp:583` and `:590`. Rows `identity/{reader,writer}` and `allocated/reader-sub`.

```python
import csv
class Sub(type(csv.reader([]))):
    def __init__(self): print("init")
print("subclass")
try:
    x = Sub()
    print("made")
except TypeError: print("TypeError")
```

CPython prints `subclass` then `TypeError`. Bella prints `subclass`, `init`, then `made`. The writer gives the same outputs using `type(csv.writer(io.StringIO()))` as the base. Both interpreters allow declaring the subclasses. CPython leaves the allocator slot absent on the derived type. Bella checks the called class's own `disallow_instantiation` flag, then finds the inherited object allocator and calls it for a Python heap class. The allocation sweep also obtained an iterator from the resulting reader subclass.

## A35-13 · Medium · Reinitializing a closed BytesIO reopens it for inputs CPython treats differently

`runtime/prelude/_io.py:2245`–`2250`. Rows `reinit/iobc0` and `bytesinit/{none,sub,array}`.

```python
import io
s = io.BytesIO(b"old")
s.close()
try: s.__init__(None); print("ok")
except BaseException as e: print(type(e).__name__)
print(s.closed)
```

CPython prints `ok` then `True`. Bella prints `ok` then `False`. With a bytes subclass instance or a bytearray containing `b"ab"` in place of None, CPython prints `ValueError` then `True`, while Bella prints `ok` then `False`. With no argument, the more detailed `iobc0` row prints `None, True, ValueError, ValueError, 1` on separate lines under CPython and `None, False, 0, b'', 1` under Bella (return, closed, tell, getvalue, preexisting instance attribute). In `Modules/_io/bytesio.c:1084`, an absent argument or None resets position and size but leaves the buffer pointer alone. An exact bytes object replaces the pointer, while other buffers take the write path and encounter the closed check. Bella installs a new bytearray in each successful path.

## A35-14 · Medium · A wrapper dictionary subclass can replace a cached annotation or prevent its deletion

`runtime/prelude/builtins.py:485`–`499`. Rows `bootstrap/{wrapread,wrapwrite,wrapdel}`. This occurs after the wrapper's real instance dictionary has been obtained, independently of A35-01.

```python
class D(dict):
    def __contains__(self, key): print("contains"); return False
    def __setitem__(self, key, value):
        print("set")
        return super().__setitem__(key, value)
    def __getitem__(self, key):
        print("get")
        return super().__getitem__(key)
    def __iter__(self): return iter(())
def f(): pass
x = staticmethod(f)
d = D()
x.__dict__ = d
x.__annotations__ = {"a": 1}
print(x.__annotations__)
print(dict.copy(d))
```

| Row | CPython stdout lines | Bella stdout lines |
|---|---|---|
| wrapwrite | `{'a': 1}`, `get`, `{'__annotations__': {'a': 1}}` | `set`, `contains`, `set`, `{}`, `get`, `{'__annotations__': {}}` |
| wrapread (omit assignment) | `{}`, `get`, `{'__annotations__': {}}` | `contains`, `set`, `{}`, `get`, `{'__annotations__': {}}` |
| wrapdel (seed by dict.__setitem__, delete the annotation, print the copy or caught exception class) | `{}` | `contains`, `AttributeError` |

CPython's descriptor helpers use PyDict_GetItemRef, PyDict_SetItem and PyDict_DelItem. Bella uses membership, subscription, assignment and deletion through the dictionary subclass. The `get` lines in the first two CPython runs come from printing the final dictionary copy.

## A35-15 · High · Reinitializing BufferedRWPair closes the old raw stream or leaves the old reader usable after failure

`runtime/prelude/_io.py:2111`–`2112`. Rows `io_state/{pairgood,pairbad}`. Minimal program for both:

```python
import io
a, b = io.BytesIO(b"old"), io.BytesIO(b"new")
p = io.BufferedRWPair(a, a)
try: p.__init__(b, b, size)  # 4 or 0
except ValueError: print("init failed")
print(a.closed)
try: print(p.read(1))
except ValueError: print("read failed")
```

With size 4, CPython prints `False` then `b'n'`. Bella prints `True` then `b'n'`. With size 0, CPython prints `init failed`, `False`, `read failed`. Bella prints `init failed`, `False`, `b'o'`. In `Modules/_io/bufferedio.c:2274` the C assignments overwrite the old pointers without decrementing them, and a reader constructor failure stores NULL. Bella's assignments release the replaced wrappers on success (closing the old raw stream), and leave the previous reader in place if evaluating the right-hand side raises.

## A35-16 · Medium · IncrementalNewlineDecoder changes state before parsing translate and releases its previous fields in reverse order

`runtime/prelude/_io.py:2553`–`2557`. Rows `io_state/{translate,order}`.

```python
import io
class Flag:
    def __bool__(self): print("bool"); raise KeyError
d = io.IncrementalNewlineDecoder(None, True)
print(repr(d.decode("before\r")))
try: d.__init__(None, Flag())
except KeyError: pass
try: print(d.getstate())
except ValueError: print("no state")
```

CPython prints `'before'`, `bool`, `(b'', 1)`. Bella prints `'before'`, `bool`, `no state`. The pending carriage return survives the failed argument conversion in CPython. Its clinic wrapper converts translate before entering the initializer. Bella marks the decoder uninitialized first.

For the successful replacement row, use the following program:

```python
import io
class V:
    def __init__(self, k): self.k = k
    def __del__(self): print("drop", self.k)
d = io.IncrementalNewlineDecoder(V("decoder"), False, V("errors"))
d.__init__(None, True)
print("done")
```

CPython prints `drop errors`, `drop decoder`, `done`. Bella prints `drop decoder`, `drop errors`, `done`. The C initializer in `Modules/_io/textio.c:261` replaces errors first.

## A35-17 · Medium · A deque iterator snapshots the deque before converting its start position

`runtime/prelude/_collections.py:746`–`747`. Rows `arg_order/{forward,reverse,zero}`.

```python
from collections import deque
d = deque([1, 2, 3])
class Index:
    def __index__(self):
        print("index")
        d.append(4)
        return 1
try: print(list(type(iter(d))(d, Index())))
except RuntimeError: print("RuntimeError")
```

CPython prints `index` then `[2, 3, 4]`. With the reverse iterator type it prints `index` then `[3, 2, 1]`. With the forward iterator and a returned index of zero it prints `index` then `[1, 2, 3, 4]`. Bella prints `index` then `RuntimeError` for each. CPython parses the index before constructing either iterator (`Modules/_collectionsmodule.c:2011` and `:2161`). Bella saves the earlier mutation counter.

## A35-18 · Medium · Reporting a bad class namespace calls its type's metaclass

`runtime/prelude/build_class.py:45` and `:119`. Row `arg_order/prepare`.

```python
class MM(type):
    @property
    def __flags__(cls):
        print("flags")
        raise LookupError
class Bad(metaclass=MM): pass
class Meta(type):
    @classmethod
    def __prepare__(m, n, b): return Bad()
try:
    class X(metaclass=Meta): pass
except BaseException as e: print(type(e).__name__)
```

CPython prints `TypeError`. Bella prints `flags` then `LookupError`. The malformed namespace is recognized on both sides. Bella's local type-name formatter then reads the metaclass property while building its diagnostic. CPython's `builtin___build_class__` reads the namespace type's C name.

## A35-19 · Medium · AST reduction and replacement iterate field names and dispatch dictionary methods

`runtime/prelude/_ast.py:209`–`210` and `:225`–`227`. Rows `ast_state/{red,replace}-{names,dict}`. Minimal shared setup:

```python
import ast
class Fields(tuple):
    def __len__(self): print("size"); return 1
    def __getitem__(self, i): print("item", i); return "x"
    def __iter__(self): print("iter"); raise LookupError
class D(dict):
    def __contains__(self, k): print("contains"); raise KeyError
class A(ast.AST):
    _fields = Fields(("x",))  # use plain ("x",) for the dict rows
    _attributes = ()
    def __init__(self, **kw): self.x = kw.get("x", 9)
    @property
    def __dict__(self): return {"x": 3}  # use D(x=3) for the dict rows
```

For reduction print `len(r), r[1]` where `r=A().__reduce__()`. For replacement print `A().__replace__().x`. Catch and print the exception class.

| Row | CPython stdout lines | Bella stdout lines |
|---|---|---|
| red-names | `size`, `item 0`, `3 (None,)` | `iter`, `LookupError` |
| replace-names | `size`, `item 0`, `3` | `iter`, `LookupError` |
| red-dict | `3 (None,)` | `contains`, `KeyError` |
| replace-dict | `3` | `contains`, `KeyError` |

CPython uses PySequence_Size followed by indexed reads, and PyDict_GetItemRef for each field. Bella loops over the names and asks the dictionary whether it contains each name.

## A35-20 · Medium · AST state methods conflate absent metadata with a present None

`runtime/prelude/_ast.py:201`–`206` and `:220`–`224`. Same A as A35-19 with ordinary `_fields=("x",)` and a plain dictionary returned by the property. Set either `_fields=None` or the dictionary property's return value to None. The print calls are the same as in A35-19.

| Row | CPython stdout | Bella stdout |
|---|---|---|
| ast_state/red-nonefields | TypeError | 3 () |
| ast_state/replace-nonefields | TypeError | 9 |
| ast_state/red-nonedict | SystemError | 2 () |
| ast_state/replace-nonedict | SystemError | 9 |

`PyObject_GetOptionalAttr` distinguishes a missing attribute from a successful lookup of Py_None. CPython then attempts to take the size of None or to read a dictionary entry from it. Bella uses None as its missing-attribute sentinel and produces a successful result.

## A35-21 · Medium · AST replacement reads the instance dictionary before its class metadata

`runtime/prelude/_ast.py:220`–`222`. Row `ast_state/replace-order`.

```python
import ast
class M(type):
    @property
    def _fields(cls): print("fields"); return ("x",)
    @property
    def _attributes(cls): print("attrs"); return ()
class A(ast.AST, metaclass=M):
    def __init__(self, **kw): self.x = kw.get("x", 9)
    @property
    def __dict__(self): print("dict"); return {"x": 3}
print(A().__replace__().x)
```

CPython prints `fields`, `attrs`, `dict`, `3`. Bella prints `dict`, `fields`, `attrs`, `3`. `ast_type_replace` in `Python/Python-ast.c:5614` obtains both class attributes first. All three reads can execute user code.

## A35-22 · High · OSError ignores the errno object's hash and equality when choosing the exception class

`runtime/src/types.cpp:2242`. Rows `construction/{errnomap,errnoerr}`.

```python
import errno
class Code(int):
    def __hash__(self): print("hash"); return errno.ENOENT
    def __eq__(self, other): print("eq", other); return True
try: print(type(OSError(Code(errno.EACCES), "msg")).__name__)
except BaseException as e: print(type(e).__name__)
```

CPython prints `hash`, `eq 2`, `FileNotFoundError`. If the hash logs and raises LookupError, CPython prints `hash` then `LookupError`. Bella prints only `PermissionError` in both rows. CPython's `Objects/exceptions.c:2231` looks up the original int subclass instance in the errno dictionary. Bella extracts the integer value and switches on it. The ordinary errno sweep from 1 through 134 agreed.

## A35-23 · Medium · BlockingIOError exposes a characters_written value of minus one

`runtime/src/types.cpp:2377`–`2380`. Row `construction/missing`.

```python
for n in (-1, -2, 0, 1):
    e = BlockingIOError(1, "m", n)
    try: print(e.characters_written)
    except AttributeError: print("AttributeError")
```

CPython prints `AttributeError`, `-2`, `0`, `1`. Bella prints `-1`, `-2`, `0`, `1`. CPython's getter treats the stored integer -1 as the absence marker (`Objects/exceptions.c:2437`). Bella only treats an unset object slot as absent.

## A35-24 · Medium · AST initialization asks for a positional field name twice

`runtime/prelude/_ast.py:160`–`161`. Row `construction/field`.

```python
import ast
class T(tuple):
    def __getitem__(self, i): print("get", i); return super().__getitem__(i)
class X(ast.AST): _fields = T(("v",))
print(X(3).v)
```

CPython prints `get 0` then `3`. Bella prints `get 0` twice then `3`. The C initializer keeps the name obtained by PySequence_GetItem across both the attribute store and the removal from the remaining-fields set. Bella indexes `fields[i]` anew for each operation.

## A35-25 · Medium · AST initialization uses subclass membership to obtain a field's declared type

`runtime/prelude/_ast.py:181`–`183`. Row `construction/table`.

```python
import ast
class D(dict):
    def __contains__(self, k): print("contains"); raise KeyError
class X(ast.AST):
    _fields = ("v",)
    _field_types = D(v=list[int])
try: print(X().v)
except KeyError: print("KeyError")
```

CPython prints `[]`. Bella prints `contains` then `KeyError`. CPython uses PyDict_GetItemWithError to read the declaration and initializes a list field. Bella calls the membership and subscription protocols of the supplied dictionary.

## Coverage and matching checks

The probe archive contains 26 builds. Across 610 paired rows that completed without a named stop, 520 matched byte for byte on stdout, stderr and exit status. Rows include exploratory runs, controls and reductions of the same observation. Two initial allocation drivers encountered a named stop during common setup. The corrected `allocated` driver reached the individual cases. A preliminary pattern driver encountered the class-building finding before its selected pattern; `patterns` and `factory` isolated the operations.

- All 176 `iteration` rows agreed. They exercised iterator acquisition, calls to next, resumption after a valued StopIteration, KeyError, GeneratorExit and KeyboardInterrupt, and iterator destruction. For exceptions escaping a consumer, the probe also printed traceback length and context/cause classes. The consumers included dict construction/update, sets, sequences, unpacking, starred calls, short-circuiting builtins, reduce, stream and CSV writes, and the itertools operations listed in the program. All five `depth` rows hit RecursionError after 79 entries under a limit of 80.
- Of the 183 allocation rows in the corrected driver, 179 agreed. These compared direct object allocation, the type's own allocator, and a subclass skipping base initialization; the program then queried applicable state and common operations. The two named stops and the already-open Struct allocator case are outside the findings. The new differential there was CSV reader subclass instantiation.
- All 30 evaluator rows agreed for formats 0 through 5, including the raised exception classes for unsupported calls. The cases covered a lazy bound, constraints, default, alias value and an eager bound. GenericAlias calling and the nested-list parameter control also agreed.
- All 18 `metadata` and eight `pending` rows agreed. These included explicit chaining, failing cause construction, generator throw and close, exception state restoration, custom exception-group split/derive and except-star, and AST repr on missing, cyclic, list, tuple and depth-limited fields. Class and instance repr after assigning str-subclass names, copy of an instance, and the TextIOWrapper operations after close and detach also agreed.
- The 12 numbered unraisable-hook rows agreed through successive sink failures and through successful completion. The reinitialization controls agreed on all 12 OSError cases, six SyntaxError argument shapes and all six StringIO cases. Exact bytes reopened a closed BytesIO on both sides. All nine callback rows agreed, including signal handler installation/retrieval/restoration, atexit registration, callable rejection, Context.run, the weak proxy call and thread-local reinitialization.
- Sentinel repr/reduction/copy, union equality, the struct-sequence iterator and wrong-receiver controls, SimpleNamespace construction/replacement, AST reduction/replacement through a raising dictionary property, and partial calling through an overridden public args property agreed. All four focused buffered-stream weak-reference release checks agreed. Some broader buffered rows differed only in finalizer output after errors had unwound; the focused checks did not establish a separate cause, so those traces contribute no additional finding.

Coverage is sampled. In particular, the allocator sweep exercised representative methods and return types; it was not a method-by-method proof for each type. The source scan covered all 54 prelude files, with detailed C comparison concentrated on the paths exercised above.
