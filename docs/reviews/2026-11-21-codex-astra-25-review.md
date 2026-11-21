Codex `gpt-6.2-astra` at low reasoning effort, 2026-11-21, the cross-check the author asked for after each step. Verbatim. Tag A25 in the
review log. Its range is `729cd7b..30ad3a9`, run non-interactively (standard input closed) in its own worktree (`bella-r25`) at `30ad3a9`: the
order in which a built-in type lets go of what it holds (RL-565, RL-577) first, then the fixes of A24 and the streams' state methods. Its
probes (`r25-probes/codex/`) stayed in that worktree. Twenty-two findings; each program was run on both sides by the session before any
verdict (review log, A25).

---

# Bella conformance review A25

Reviewed 729cd7b..30ad3a9 in the detached checkout and compared compiled programs with CPython 3.15.2 under PYTHONHASHSEED=0. The findings describe behavior at the tip. A file reference identifies the responsible path without implying that the range introduced the defect. Unless stated otherwise both processes exited 0 with empty stderr. Reproductions below isolate the relevant rows of the grouped probes in `r25-probes/codex/`.

**Highest impact.** A25-20 skips user finalizers. A25-06 reads stale bytes and allows a resize while a struct iterator owns the buffer. A25-03 returns the wrong exception state to serialization clients. A25-18 changes a closed stream back into a usable one. A25-22 shows the multiple-inheritance layout fix still selects the wrong base for a prelude type.

## A25-01 · Medium · A regex scanner releases its pattern before its subject

`runtime/prelude/_sre.py:696`, `runtime/src/call.cpp:1893`. CPython's scanner_dealloc runs state_fini (releasing the subject) before scanner_clear (releasing the pattern). Bella clears the two slots in declaration order. Purging the regex cache makes the scanner the last owner of the pattern.

```python
import re, weakref
events = []
class S(str):
    def __del__(self): events.append(str(self))
p = re.compile(S("a"))
re.purge()
w = weakref.ref(p, lambda r: events.append("pattern"))
s = p.scanner(S("abc"))
del p, s
print(events)
```

CPython: `['abc', 'pattern', 'a']`  
Bella: `['pattern', 'a', 'abc']`

## A25-02 · Medium · A function retains its writable __module__ past its defaults

`runtime/src/core.cpp:237`. The explicit cleanup releases the defining module and the defaults, but leaves the Python-visible module name to the C++ destructor. CPython's func_clear clears func_module before func_defaults.

```python
events = []
class V:
    def __init__(self, n): self.n = n
    def __del__(self): events.append(self.n)
def make():
    v = V("closure")
    def f(a=V("default"), *, k=V("kw")): return v
    f.__doc__ = V("doc")
    f.__module__ = V("module")
    f.x = V("dict")
    return f
import weakref
f = make()
w = weakref.ref(f, lambda r: events.append("weak"))
del f
print(events)
```

CPython: `['weak', 'module', 'default', 'kw', 'doc', 'dict', 'closure']`  
Bella: `['weak', 'default', 'kw', 'doc', 'dict', 'closure', 'module']`

## A25-03 · High · Exception reduction silently substitutes a class attribute for instance state

`runtime/src/types.cpp:2226` (BaseException), `:2211` (OSError), `:2236` (the shared state helper). The reducer correctly checks whether the instance has allocated a dict, then performs ordinary attribute lookup for its contents. A subclass can shadow that lookup. This changes the serialized state returned to callers even when the real dictionary already contains data.

```python
for base in (Exception, OSError, ImportError, AttributeError):
    class E(base):
        __dict__ = {'fake': 1}
    e = E('a')
    e.x = 2
    print(base.__name__, e.__reduce__()[2])
```

| Base | CPython state | Bella state |
|---|---|---|
| Exception | `{'x': 2}` | `{'fake': 1}` |
| OSError | `{'x': 2}` | `{'fake': 1}` |
| ImportError | `{'x': 2}` | `{'fake': 1}` |
| AttributeError | `{'x': 2, 'args': ('a',)}` | `{'fake': 1, 'args': ('a',)}` |

## A25-04 · Medium · ContextVar releases its default before its name

`runtime/prelude/_contextvars.py:259`. Bella declares the default before the name. CPython’s contextvar_tp_clear clears var_name first. A str subclass makes the name’s release visible.

```python
import contextvars as c
events=[]
class V:
    def __init__(self,n): self.n=n
    def __del__(self): events.append(self.n)
class S(str):
    def __del__(self): events.append(str(self))
def var():
    x=c.ContextVar(S("name"),default=V("default"))
    del x
var()
print(events)
```

CPython: `['name', 'default']`  
Bella: `['default', 'name']`

## A25-05 · Medium · Token releases the old value before its variable

`runtime/prelude/_contextvars.py:379`. After the context goes, CPython’s token_tp_clear drops tok_var before tok_oldval. Bella declares _old before _var. The variable owns the only reference to its default.

```python
import contextvars as c
events=[]
class V:
    def __init__(self,n): self.n=n
    def __del__(self): events.append(self.n)
def tok():
    ctx=c.Context()
    def make():
        x=c.ContextVar("x",default=V("default"))
        x.set(V("old"))
        return x.set(None)
    t=ctx.run(make)
    del ctx,t
tok()
print(events)
```

CPython: `['default', 'old']`  
Bella: `['old', 'default']`

## A25-06 · High · Struct.iter_unpack snapshots a mutable input and loses the exporter

`runtime/prelude/_struct.py:75`, `:588`. _buffer converts the exporter to bytes. CPython keeps a Py_buffer on the exporter until exhaustion or iterator destruction. A write to an existing byte must be visible through the iterator, and resizing must raise BufferError. In a separate row (owners.py, st), an input bytes subclass and a weakref on the Struct recorded `['struct', 'buffer']` on CPython and `['buffer', 'struct']` on Bella.

```python
import struct
events=[]
def unpack():
    b=bytearray(b'ab')
    s=struct.Struct("B")
    it=s.iter_unpack(b)
    b[0]=65
    print(next(it))
    try: b.extend(b'x');print("resized")
    except BufferError: print("pinned")
unpack()
```

CPython: `(65,) then pinned`  
Bella: `(97,) then resized`

## A25-07 · Medium · dict and OrderedDict item iterators release the yielded value too soon

`runtime/src/ops.cpp:1983`, `runtime/prelude/_collections.py:1365`. Both paths return a fresh pair and keep no result tuple. CPython’s di_result retains the most recently recycled pair, so its value survives clearing the mapping.

```python
from collections import OrderedDict
events=[]
class V:
    def __init__(self,n): self.n=n
    def __del__(self): events.append(self.n)
def items(k):
    d=k(a=V("v"))
    it=iter(d.items())
    next(it)
    d.clear()
    events.append("clear")
    del it
for cls in (dict, OrderedDict):
    events.clear()
    items(cls)
    print(events)
```

CPython: `['clear', 'v'] (twice)`  
Bella: `['v', 'clear'] (twice)`

## A25-08 · Medium · BufferedRWPair closes its writer before its weak references fire

`runtime/include/bella/object.hpp:2035`, `runtime/prelude/_io.py:357`, `:2011`. Bella runs the inherited IOBase finalizer, which calls the pair’s close (writer then reader). CPython’s bufferedrwpair_dealloc clears weakrefs directly, then lets the buffered reader and writer die in turn. User raw streams can observe every close.

```python
import io, weakref
events=[]
class V:
    def __init__(self,n): self.n=n
    def __del__(self): events.append(self.n)
class Raw(io.BytesIO):
    def __init__(self,n): super().__init__();self.n=n
    def close(self): events.append("close "+self.n);super().close()
    def __del__(self): events.append("del "+self.n)
def pair():
    p=io.BufferedRWPair(Raw("r"),Raw("w"))
    p.x=V("dict")
    w=weakref.ref(p,lambda r:events.append("weak"))
    del p
pair()
print(events)
```

CPython: `['weak', 'close r', 'del r', 'close w', 'del w', 'dict']`  
Bella: `['close w', 'close r', 'weak', 'del r', 'del w', 'dict']`

## A25-09 · Medium · A function releases its closure cells in forward order

`runtime/src/core.cpp:240`, `:245`. Releasing closure_tuple leaves references in the C++ closure vector, which the loop clears from front to back. CPython drops the owning tuple and its cells die from last to first. This needs no closure cycle.

```python
events=[]
class V:
    def __init__(self,n): self.n=n
    def __del__(self): events.append(self.n)
def closure():
    def create():
        a=V("a"); b=V("b");c=V("c")
        def f():return a,b,c
        return f
    f=create()
    del f
closure()
print(events)
```

CPython: `['c', 'b', 'a']`  
Bella: `['a', 'b', 'c']`

## A25-10 · Medium · The unbounded LRU wrapper releases its function before cached entries

`runtime/prelude/_functools.py:496`. The release order follows _l_func before _l_cache. CPython’s lru_cache_tp_clear releases the cache first. Using the wrapper directly avoids the additional __wrapped__ reference installed by functools.update_wrapper. Neither the key nor the result points back to the cache.

```python
import _functools
events=[]
class V:
    def __init__(self,n): self.n=n
    def __del__(self): events.append(self.n)
class F(V):
    def __call__(self,*args): return V("result")
def cache():
    f=_functools._lru_cache_wrapper(F("func"),None,False,tuple)
    f(V("key"))
    del f
cache()
print(events)
```

CPython: `['key', 'result', 'func']`  
Bella: `['func', 'key', 'result']`

## A25-11 · Medium · Slot construction skips a user-defined comparison

`runtime/src/types.cpp:783`, `runtime/include/bella/object.hpp:943`. Bella converts names to text and sorts by UTF-8 bytes. CPython’s type_new_copy_slots calls PyList_Sort on the mangled names, which still hold the original str subclasses for public names. The comparison has side effects and decides the order of the member descriptors.

```python
class T(str):
    def __lt__(self, other):
        print("compare", str(self), str(other))
        return super().__gt__(other)
class D:
    __slots__ = (T("a"), T("b"))
print([n for n in vars(D) if n in ("a", "b")])
```

CPython prints `compare b a` followed by `['b', 'a']`. Bella prints only `['a', 'b']`.

## A25-12 · Low · A private slot conflict names the unmangled member

`runtime/src/types.cpp:785`. The comparison uses the mangled spelling, but the diagnostic interpolates the original spelling. CPython reports the member key it looked up.

```python
try:
    class A:
        __slots__ = ("__x",)
        __x = 1
except ValueError as e:
    print(type(e).__name__, str(e))
```

CPython: `ValueError '_A__x' in __slots__ conflicts with class variable`  
Bella: `ValueError '__x' in __slots__ conflicts with class variable`

## A25-13 · Low · Variable-size slot diagnostics name the wrong base

`runtime/src/types.cpp:792`. Bella formats the name of the built-in type found by its ancestry check. CPython formats ctx->base->tp_name, which can be the immediate user-defined base.

```python
for base in (int, bytes):
    class Parent(base):
        __slots__ = ()
    try:
        class Child(Parent):
            __slots__ = ("x",)
    except TypeError as e:
        print(type(e).__name__, str(e))
```

CPython prints `TypeError arbitrary __slots__ not supported for subtype of 'Parent'` twice. Bella prints the same message ending in `'int'` and then `'bytes'`.

## A25-14 · Medium · Duplicate slots in one declaration bypass the default reducer’s size check

`runtime/src/types.cpp:786`, `:3017`. The slot builder deduplicates names before computing the layout. CPython allocates two cells even though only one member is accessible. One supplied slot name therefore accounts for too little storage under CPython.

```python
import copyreg
class Dup:
    __slots__ = ("x", "x")
    __slotnames__ = ["x"]
d = Dup()
d.x = 1
try:
    print(d.__reduce_ex__(4)[2])
except TypeError as e:
    print(type(e).__name__, str(e))
```

CPython: `TypeError cannot pickle 'Dup' object`  
Bella: `(None, {'x': 1})`

## A25-15 · Medium · A class with enough explicit slot names still fails default reduction

`runtime/prelude/bootstrap.py:2140`, `runtime/src/types.cpp:3012`. CPython’s required-state test compares the actual basic size with the storage accounted for by the number of supplied names. Repeated and missing names still contribute to that count. Bella treats any fixed-size native base classified as having state as an unconditional failure. The probe also reproduced this with staticmethod and classmethod subclasses.

```python
import copyreg
class X(property):
    __slots__ = ()
    __slotnames__ = ['unused'] * 64
    __reduce__ = object.__reduce__
try:
    print(X().__reduce_ex__(4)[2])
except TypeError as e:
    print(type(e).__name__, str(e))
```

CPython: `None`  
Bella: `TypeError cannot pickle 'X' object`

## A25-16 · Medium · Struct sequences release fields backwards

`runtime/include/bella/object.hpp:2124`, `runtime/src/types.cpp:2997`. Bella stores visible fields in a tuple subclass and extra fields in a separate tuple. The tuple destructor walks backwards. CPython’s structseq_dealloc walks the complete physical field array from index zero upwards. This also reproduced for os.stat_result with fields beyond its visible tuple.

```python
import os
events = []
class V:
    def __init__(self, n): self.n = n
    def __del__(self): events.append(self.n)
t = os.terminal_size((V("columns"), V("lines")))
del t
print(events)
```

CPython: `['columns', 'lines']`  
Bella: `['lines', 'columns']`

## A25-17 · Medium · Exhausting a Context iterator drops the mapping too soon

`runtime/prelude/_contextvars.py:87`. The wrapper stores a dict iterator and the mapping length. Once exhausted, that dict iterator releases the dict. CPython’s HAMT iterator keeps the mapping alive until the iterator itself dies. The lifetime difference occurs for keys, values and items.

```python
import contextvars as c
events = []
class V:
    def __del__(self): events.append("v")
for kind in ("keys", "values", "items"):
    events.clear()
    cx = c.Context()
    cx.run(c.ContextVar("k").set, V())
    it = getattr(cx, kind)()
    del cx
    list(it)
    events.append("exhausted")
    del it
    print(events)
```

CPython: `['exhausted', 'v']` three times  
Bella: `['v', 'exhausted']` three times

## A25-18 · High · Restoring state reopens a closed in-memory stream

`runtime/prelude/_io.py:2297`, `:3474`. Both implementations enter the stream initializer on a closed receiver, restore the data and install the supplied dictionary. CPython’s StringIO setter checks CLOSED before parsing the tuple. Its BytesIO setter writes through the internal write implementation, which checks the closed buffer.

```python
import io
class B(io.BytesIO):
    __dict__ = "hidden"
class S(io.StringIO):
    __dict__ = "hidden"
for k, state in ((B, (b"ok", 1, {"v": 2})), (S, ("ok", None, 1, {"v": 2}))):
    o = k()
    o.close()
    try: o.__setstate__(state)
    except Exception as e: print(type(e).__name__, str(e))
    print(o.closed, o.__dict__, None if o.closed else o.__getstate__())
```

CPython stdout:
```text
ValueError I/O operation on closed file.
True hidden None
ValueError I/O operation on closed file
True hidden None
```

Bella stdout:
```text
False hidden (b'ok', 1, {'v': 2})
False hidden ('ok', None, 1, {'v': 2})
```

## A25-19 · Medium · BytesIO accepts None as the buffer in a restored state

`runtime/prelude/_io.py:2297`, `:2103`. BytesIO.__init__ accepts None as an empty initial value. CPython’s state setter requires a buffer even for an empty payload. Bella goes on to install the supplied dictionary after accepting None.

```python
import io
class B(io.BytesIO):
    __dict__ = "hidden"
o = B()
try: o.__setstate__((None, 0, {"v": 2}))
except Exception as e: print(type(e).__name__, str(e))
print(o.closed, o.__dict__, o.__getstate__())
```

CPython prints `TypeError a bytes-like object is required, not 'NoneType'`, then `False hidden (b'', 0, None)`. Bella prints only `False hidden (b'', 0, {'v': 2})`.

## A25-20 · High · Descriptor-based finalizers never execute

`runtime/include/bella/object.hpp:2035`, `runtime/src/call.cpp:3160`. The runtime finds the raw class-dict entry and passes the instance to it as a positional argument. CPython binds the special method through the descriptor protocol. The following program observes the otherwise unraisable failures through the normal hook. A descriptor with a custom __get__ also failed to bind in the grouped probe.

```python
import sys
def hook(e): print("unraisable", e.exc_type.__name__, str(e.exc_value))
sys.unraisablehook = hook
class S(list):
    @staticmethod
    def __del__(): print("static")
class C(list):
    @classmethod
    def __del__(cls): print("class", cls.__name__)
for k in (S, C):
    o = k()
    del o
```

CPython stdout:
```text
static
class C
```

Bella stdout:
```text
unraisable TypeError S.__del__() takes 0 positional arguments but 1 was given
unraisable TypeError 'classmethod' object is not callable
```

## A25-21 · Medium · Exact BytesIO and StringIO call an instance’s close hook on destruction

`runtime/include/bella/object.hpp:2035`, `runtime/prelude/_io.py:357`. The common finalizer dispatch runs IOBase.__del__ on both exact types, which calls the instance’s close hook. CPython’s bytesio_dealloc and stringio_dealloc directly clear storage, the dict and weakrefs. Installing the hook on the exact instance makes the extra call visible without introducing a reference cycle.

```python
import io, weakref
for k in (io.BytesIO, io.StringIO):
    o = k()
    o.close = lambda: print("close")
    w = weakref.ref(o, lambda r: print("weak"))
    del o
```

CPython prints `weak` twice. Bella prints `close`, `weak`, `close`, `weak` on successive lines.

## A25-22 · Medium · A mixin wins __base__ over SimpleNamespace and changes the descriptors installed

`runtime/src/types.cpp:498`, `:700`, `:836`. solid_base recognizes ordinary slots and the runtime’s native layouts. SimpleNamespace is implemented as a heap class with only a dict slot, which own_slot_names excludes. Bella therefore treats its layout as equivalent to object’s and breaks the tie in favor of the first base. CPython recognizes the namespace’s C layout. The effect reaches the new class’s own dict and weakref descriptors. The same base-selection error reproduced with io.IOBase and io.RawIOBase in place of SimpleNamespace.

```python
from types import SimpleNamespace
class W:
    __slots__ = ('__weakref__',)
class X(W, SimpleNamespace):
    __slots__ = ()
print(X.__base__.__name__, '__dict__' in vars(X), '__weakref__' in vars(X))
```

CPython: `SimpleNamespace False True`  
Bella: `W True False`

## Checks that agreed

- **Native exception fields.** The 288 stdout lines from `all_exc.py` agreed byte for byte. It declared an exception subclass for each available built-in exception name, shadowed its native member/getset names with assigned slots, then raised it from a cause and compared str, repr, reduction and copy. The separate explicit excepthook probe with empty cause, context and suppression slots agreed on the chain and messages after accounting for D-06.
- **Two levels of inheritance.** Deleting a base slot, dropping the instance and observing the remaining derived slot, dict and weakrefs agreed for dict, list, tuple, set, deque, property with an explicit doc, staticmethod, classmethod, partial, BytesIO and SimpleNamespace. A BytesIO subclass’s finalizer could read its value and its slot, save the object and keep the weakref live until the saved reference was dropped. A deque’s weakref.finalize callback could retain a held item through an independent weakref. An aliased empty slot agreed on both its message and AttributeError.name for getattr, object.__getattribute__ and the descriptor’s own __get__.
- **Streams and scanners.** BufferedWriter, BufferedRandom and TextIOWrapper agreed on raw close, weak callback, raw destruction and instance-dict value destruction. IncrementalNewlineDecoder released a user decoder before its errors argument. Closed FileIO agreed on weakref, path and dict release. For a live stream, BytesIO and StringIO both retained the state dict subclass by identity and invoked its keys and __getitem__ when copying state out. The CSV reader agreed on delimiter, quote character and line-terminator subclass lifetimes. The regex match agreed on subject, pattern weakref and pattern-text destruction.
- **Other owners.** The probes agreed for TypeVar and ParamSpec with a bound, default and instance attribute, TypeAliasType with a named type parameter, cmp_to_key with a separate comparator and value, and a weakref.ref subclass with its own slot, dict and weak callback. They also agreed for a suspended generator’s weakref, finally block and two local finalizers, list/tuple/str/set iterator exhaustion, random.Random, thread-local storage in a single thread, lock and RLock, zlib’s decompression dictionary, SHA-256 weakref rejection, scandir and DirEntry path lifetimes, and SimpleNamespace weakref rejection.
- **Startup diagnostics.** For Latin-1 coding-cookie sources with a leading form feed, a 650-digit integer, no final newline and a final line of exactly 999 or 1000 bytes, both executables exited 1 with empty stdout and byte-identical stderr at PYTHONINTMAXSTRDIGITS=640. The Bella executables were built at the default limit and then launched at 640. The NUL-byte source was rejected during the build and produced no executable to compare.
