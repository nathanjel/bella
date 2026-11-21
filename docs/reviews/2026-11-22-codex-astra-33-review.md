Codex `gpt-6.2-astra` at low reasoning effort, 2026-11-22, the cross-check the author asked for after each step. Verbatim. Tag A33 in the
review log. Its range is `f8203de..6bd852a`, run non-interactively (standard input closed) in its own worktree (`bella-r33`) at `6bd852a`: the
fixes of review A32 (RL-703 to RL-722), the names of `__slots__` sorted as objects (RL-588) and the list of names beyond CPython's. Its
probes (`r33-probes/codex/`) stayed in that worktree. 27 findings; each was run on both sides by the session before any verdict (review
log, A33).

---

# A33 conformance review of f8203de..6bd852a

27 findings from 23 builds and 5,722 paired runs. Of those pairs, 5,144 matched stdout, stderr and exit status byte for byte. The raw mismatch count includes addresses, traceback source lines and named stops. No row timed out. The two high-severity findings, A33-14 and A33-15, both affect saved text-stream positions.

All row paths below are relative to `r33-probes/codex`. For a row `suite/row`, the two commands were `PYTHONHASHSEED=0 .venv/bin/python r33-probes/codex/suite/prog.py row` and `PYTHONHASHSEED=0 "$binary" row`, where `binary` is the path printed by `./r33-build r33-probes/codex/suite/prog.py`. Each build had a 600-second timeout and each run had a 120-second timeout and an 8000000 KiB virtual-memory limit. Each row has its own stdout, stderr and status files. The following reduced snippets give the operations exercised by those rows.

## A33-01 · Medium · IncrementalNewlineDecoder can return a 65-bit state flag

`runtime/prelude/_io.py:2509`. Row `state/flag`. Both stderr files are empty and both processes exit 0.

```python
import io
class Decoder:
    def getstate(self): return b'x', -1
print(io.IncrementalNewlineDecoder(Decoder(), True).getstate())
```

CPython prints `(b'x', 18446744073709551614)`. Bella prints `(b'x', 36893488147419103230)`. Both mask the input to an unsigned long long. CPython also wraps the left shift in that type when reserving the pending-CR bit. Bella performs that shift on a Python integer.

## A33-02 · Medium · IncrementalNewlineDecoder discards two decoder callback results

`runtime/prelude/_io.py:2530` and `:2540`. Rows `state/reset` and `state/set`. Both stderr files are empty and both processes exit 0.

```python
import io
class Decoder:
    def reset(self): return 'reset'
    def setstate(self, s): print(s); return 'set'
d = io.IncrementalNewlineDecoder(Decoder(), True)
# Run each independently
print(d.reset())
print(d.setstate((b'x', 5)))
```

For reset, CPython prints `reset` and Bella prints `None`. For setstate both print `(b'x', 2)` first, then CPython prints `set` and Bella prints `None`. The prelude calls both methods as statements. CPython returns the result of the underlying method call.

## A33-03 · Medium · JSON loses the original exception when adding a note fails

`runtime/prelude/_json.py:558`. Rows `library/json.notes.{compact,indent,skip}`. Each process exits 0 with empty stderr.

```python
import json, sys
class E(Exception): pass
def default(o):
    print(type(sys.exception()).__name__)
    e = E()
    e.__notes__ = 42
    raise e
try: raise LookupError
except LookupError:
    try: json.dumps([{'q': [object()]}], default=default)
    except BaseException as e:
        print(type(e).__name__, e.__notes__, type(e.__context__).__name__, type(e.__cause__).__name__)
```

CPython stdout:

```text
LookupError
TypeError ["when serializing dict item 'q'", 'when serializing list item 0'] E NoneType
```

Bella's last two fields are `LookupError NoneType`; the rest agrees. The first list-item note cannot be appended to the integer on E. CPython chains the resulting TypeError to E. Bella handles a failure to *format* a note explicitly, but calls `BaseException.add_note` outside that handler. Its TypeError takes the ambient LookupError as context.

## A33-04 · Medium · Six io allocators accept arguments that a subclass's super call must reject

`runtime/prelude/_io.py:1921` (BufferedReader, BufferedWriter, BufferedRandom), `:2014` (BufferedRWPair), `:2468` (IncrementalNewlineDecoder), `:2843` (TextIOWrapper). Rows `dispatch/new.<class>.new` for those six classes. Both sides exit 0 with empty stderr.

```python
import io
class New(io.BufferedReader):
    def __new__(cls, *args):
        print('new')
        return super().__new__(cls, *args)
try: print(type(New(io.BytesIO())).__name__)
except Exception as e: print(type(e).__name__)
```

Every CPython row prints `new` then `TypeError`. Every Bella row prints `new` then `New`. The RWPair row supplies two streams and the newline-decoder row supplies `None, True`. In CPython the call reaches the inherited object allocator, which checks excess arguments when the subclass overrides allocation. Each Bella class installs an allocator that accepts arbitrary arguments and initializes the prelude's fields.

There is a second observable consequence on the three classes populated by `_bf_make_methods` at `runtime/prelude/_io.py:1938`. In `remaining/{br,bw,random}.__new__.{fresh,closed}`, start with `x=io.BufferedReader(io.BytesIO())` (or the corresponding writer or random stream) and evaluate `type(x.__new__(type(x))).__name__`. CPython returns the respective class name and Bella raises TypeError. These three allocators are assigned with setattr after class creation, as ordinary functions, so instance lookup binds a receiver that CPython's allocator does not take.

## A33-05 · Medium · Buffered construction accepts a raw stream's non-boolean capability

`runtime/prelude/_io.py:284`. Representative row `library/raw.BufferedReader.readable.int`. Both exit 0 with empty stderr.

```python
import io
class I(int): pass
class Raw(io.BytesIO):
    def readable(self): return I(1)
try:
    v = io.BufferedReader(Raw(b'abcd'), 2).readable()
    print(type(v).__name__, repr(v))
except BaseException as e:
    print(type(e).__name__, getattr(e, '__notes__', None),
          type(e.__context__).__name__, type(e.__cause__).__name__)
```

CPython prints `UnsupportedOperation None NoneType NoneType`. Bella prints `I 1`. Rows with `float`, `neg` and `big` also construct the reader and return the original truthy value on Bella. CPython's capability checks require the singleton True. The prelude tests truthiness after the identity check fails. The same four truthy inputs reproduce this on BufferedWriter.writable, BufferedRandom.readable and writable, and BufferedRWPair.readable and writable (the corresponding library/raw rows).

## A33-06 · Medium · A file finalizer's repr and unraisable hook see the close error as handled

`runtime/prelude/_io.py:395`. Rows `edges/file.<class>.<repr>.<outer>` for BytesIO, StringIO, FileIO, BufferedReader and TextIOWrapper subclasses. Representative program for `file.BytesIO.ok.plain`:

```python
import io, sys
def log(tag): print(tag, type(sys.exception()).__name__)
def hook(e):
    log('hook')
    print(e.exc_type.__name__, e.err_msg, e.object is None, e.exc_traceback is None)
sys.unraisablehook = hook
class F(io.BytesIO):
    def close(self): log('close'); raise ValueError('file close')
    def __repr__(self): log('repr'); return 'file'
f = F()
del f
```

CPython stdout:

```text
close NoneType
repr NoneType
hook NoneType
ValueError Exception ignored while finalizing file file True False
```

Bella prints `repr ValueError` and `hook ValueError`; the other lines agree. When the caller handles LookupError, CPython keeps that exception visible through all three callbacks. Bella switches to ValueError after close. Both correctly pass a null message for a repr that raises or returns None. Both exit 0 with empty stderr. The prelude formats the message and invokes the hook inside its `except BaseException as e` suite. CPython has already fetched the pending close exception at that point.

The same handler-scope error occurs at `runtime/prelude/atexit.py:44`. In `detail/repr.atexit`, the callback's repr clears a list containing a marker. The marker's finalizer prints `released NoneType` on CPython and `released ValueError` on Bella. Both next print `ValueError Exception ignored in atexit callback C False True` and exit 0 with empty stderr. In `matrix/hook.atexit.good.raises` and `hook.file.good.raises`, the failing user hook consequently adds a second ValueError and the “During handling” separator to Bella's stderr.

## A33-07 · Medium · Deduplicating slot names suppresses a user comparison

`runtime/src/types.cpp:804`. Rows `matrix/slots.list.dup` and `matrix/slots.gen.dup`. Both exit 0 with empty stderr.

```python
events = []
class S(str):
    def __lt__(self, other): events.append('lt'); return [0]
names = [S('a'), S('a')]
class C: __slots__ = names
print(C.__slots__ is names, [k for k in vars(C) if k == 'a'], events)
```

CPython prints `True ['a'] ['lt']`. Bella prints `True ['a'] []`. The archived rows also print the same caught AttributeError after this observation. CPython sorts both original objects. Bella's new comparison path drops equal *text* from its sort input. The missing user callback is observable during class creation, independent of the later cell-count test in RL-591.

A reduced class-creation row, `slots/dup`, makes `S.__lt__` raise LookupError on two equal declarations. CPython prints the caught `LookupError`; Bella prints `made`. Both exit 0 with empty stderr.

## A33-08 · Medium · A failing stderr writer sees the wrong calls during unraisable reporting

`runtime/src/call.cpp:2666` and `:485`. Rows `edges/stderr.pieces` and `edges/stderr.count`. Both exit 0 with empty actual stderr. The observable output is on stdout.

```python
import sys
class Err:
    def write(self,s): print('write',repr(s)); raise KeyError('err')
    def flush(self): pass
class D:
    def __repr__(self): return 'del'
    def __call__(self): raise ValueError('broken')
class X: __del__ = D()
old = sys.stderr
sys.stderr = Err()
x = X()
del x
sys.stderr = old
print('ok')
```

CPython:

```text
write 'Exception ignored while calling deallocator del'
write 'Exception ignored in sys.unraisablehook'
ok
```

Bella:

```text
write 'Exception ignored while calling deallocator del:\n'
write 'Traceback (most recent call last):\n'
write 'Traceback (most recent call last):\n'
ok
```

CPython's first failed write ends the default hook and starts a report about the hook failure. Bella combines the message and suffix into one write, catches the writer's exception inside `write_stderr`, and continues into traceback printing.

## A33-09 · Low · Two internal deallocators are callable from Python

`runtime/prelude/itertools.py:361` and `runtime/prelude/zlib.py:542`. Rows `edges/extra.tee` and `matrix/surplus.zlib`. Each line runs separately. Each prints `False` on CPython and `True` on Bella, with empty stderr and status 0.

```python
import itertools, zlib
print(hasattr(itertools._tee_dataobject(iter([]), [], None), '__del__'))
print(hasattr(zlib._ZlibDecompressor(), '__del__'))
```

The preludes implement cleanup with a Python-visible special method. CPython keeps these deallocators in the type's internal slots.

## A33-10 · Medium · A class can derive from the type of typing.NoDefault

`runtime/prelude/_typing.py:152` and the base check at `runtime/src/types.cpp:713`. Row `edges/extra.no`.

```python
import typing
class T(type(typing.NoDefault)): pass
print('made')
```

CPython exits 1 with empty stdout and a traceback ending in `TypeError: type 'NoDefaultType' is not an acceptable base type`. Bella prints `made`, with empty stderr and status 0. The prelude class passes Bella's final-type check. CPython's type lacks the flag allowing use as a base.

## A33-11 · Medium · Slot conflict checking bypasses the slot object's hash

`runtime/src/types.cpp:784`. Row `slots/lookup`. Both exit 0 with empty stderr. The only argument to type creation here is a list of slot declarations. There is no attribute access or keyword with a subclass name.

```python
class S(str):
    def __hash__(self): print('hash'); raise ArithmeticError
try:
    class X: __slots__ = [S('a')]
    print('made')
except Exception as e: print(type(e).__name__)
```

CPython prints `hash` then `ArithmeticError`; Bella prints `made`. CPython's `type_new_copy_slots` calls `PyDict_Contains` on the namespace with the mangled name object. For an ordinary public name the object is unchanged. Bella scans the namespace comparing characters.

## A33-12 · Low · AST's generated annotation function changes an instance call's exception

`runtime/prelude/_ast.py:110`. Row `slots/ast`. Both emit the same DeprecationWarning for constructing ast.AST, and both exit 0.

```python
import ast
try: print(ast.AST().__annotate_func__(1))
except Exception as e: print(type(e).__name__)
```

CPython prints `AttributeError`. Bella prints `TypeError`. The prelude declares annotated fields in AST's class body. Its generated annotation function is available for instance binding, which supplies an extra positional argument. CPython's C class has no such function.

## A33-13 · Low · The NoDefault singleton returns implementation metadata on instance lookup

`runtime/prelude/_typing.py:152-159`. Rows `slots/extra.__firstlineno__`, `extra.__static_attributes__`, `extra.__slots__` and `extra.__module__` in that suite. Both exit 0 with empty stderr.

```python
import sys, typing
print(getattr(typing.NoDefault, sys.argv[1].split('.')[1], 'absent'))
```

CPython prints `absent` for each. Bella prints `152`, `()`, `()` and `builtins`, respectively. Instance attribute resolution finds the Python class body's explicit module and slots declarations and its compiler-generated metadata.

## A33-14 · High · TextIOWrapper can return a negative cookie that its own seek rejects

`runtime/prelude/_io.py:2769` and `:2774`. Rows `cookie/neg.tell`, `neg.round` and `{neg,high,i,index,zero}.seek`. All exit 0 with empty stderr.

```python
import codecs, io
class Dec(codecs.IncrementalDecoder):
    def getstate(self): return b'', -1
    def setstate(self,p): print('set',type(p[1]).__name__,p[1])
    def decode(self,b,final=False): return b.decode()
class Buf(io.BytesIO):
    def writable(self): return False
codecs.register(lambda n: codecs.CodecInfo(None,None,name=n,incrementaldecoder=Dec))
f = io.TextIOWrapper(Buf(b'abc'),encoding='a33flag',newline='\n')
try:
    f.read(1)
    p=f.tell(); print('tell',p)
    print('seek',f.seek(p))
except BaseException as e: print(type(e).__name__)
```

CPython prints `set int -1` twice, `tell 79228162495817593519834398721`, `set int -1`, then `seek 79228162495817593519834398721`. Bella prints the same first two lines, then `tell -18446744073709551615` and `ValueError`. Seeking directly to the valid cookie `((1<<32)-1)<<64` passes `-1` to the decoder on CPython and `4294967295` on Bella. CPython copies the signed 32-bit flag's bit pattern into and out of its cookie. Bella sign-extends during packing and unpacks the flag as unsigned.

## A33-15 · High · TextIOWrapper.tell operates on the decoder's flag object without converting it to a C int

`runtime/prelude/_io.py:3206`, `:3220` and `:2769`. Rows `cookie/{high,i,index}.{tell,round}`. All exit 0 with empty stderr. Use the A33-14 program with this flag returned in place of `-1`:

```python
class I(int):
    def __eq__(self,v): print('eq'); return False
    def __lshift__(self,v): print('shift'); return 4
flag = I(2)
```

CPython stdout in `i.round`:

```text
set int 2
set I 2
tell 36893488147419103233
set int 2
seek 36893488147419103233
```

Bella stdout:

```text
eq
set I 2
shift
set I 2
tell 5
set int 0
seek 5
```

A flag of `2**32` raises OverflowError on CPython before any setstate callback. Bella's tell returns `79228162514264337593543950337`. An object with `__index__` returning 3 works on CPython and raises TypeError on Bella. The C parses the snapshot's flag and each reconstructed flag with the signed-int converter. It restores the original saved state object at the end. Bella uses the original flag in comparisons, callback arguments and shifts along the reconstruction path.

## A33-16 · Low · Successful IOBase capability checks return None

`runtime/prelude/_io.py:358-368`. Row `reduced/check`; also the successful `io_methods/<class>.fresh._check{Readable,Writable,Seekable}` rows. Both exit 0 with empty stderr.

```python
import io
v=io.BytesIO()
print(v._checkReadable(),v._checkWritable(),v._checkSeekable())
```

CPython prints `True True True`. Bella prints `None None None`. CPython returns the validated True result when a program calls the exposed method. Bella's wrappers call the validation helper as a statement.

## A33-17 · Medium · Inherited protocol-2 reduction accepts objects whose internal state it cannot represent

`runtime/src/types.cpp:3037` and `runtime/prelude/bootstrap.py:2138`. Reduced rows `reduced/reduce.{struct,chain,blake}`. Both exit 0 with empty stderr.

```python
import struct
o=struct.Struct('b')
try: print(o.__reduce_ex__(2)[2:])
except Exception as e: print(type(e).__name__)
```

CPython prints `TypeError`. Bella prints `(None, None, None)` for the state and two iterators. The other two reduced rows use an itertools.chain and a BLAKE2b object. These are exact instances with no user-supplied slot list. CPython's default reduction checks whether the layout can be represented. Bella consults a table keyed by type name to identify unrepresented state, and these types pass its check. The full-tuple rows include `remaining/newline.__reduce_ex__.fresh`, `inherited/acc.__reduce_ex__`, `inherited/batched.__reduce_ex__`, `inherited/blake.__reduce_ex__`, `inherited/chain.__reduce_ex__`, `inherited/comb.__reduce_ex__`, `inherited/compressiter.__reduce_ex__`, `inherited/count.__reduce_ex__`, `inherited/cwr.__reduce_ex__`, `inherited/cycle.__reduce_ex__`, `inherited/drop.__reduce_ex__`, `inherited/encoder.__reduce_ex__`, `inherited/filterfalse.__reduce_ex__`, `inherited/groupby.__reduce_ex__`, `inherited/pair.__reduce_ex__`, `inherited/perm.__reduce_ex__`, `inherited/prod.__reduce_ex__`, `inherited/repeat.__reduce_ex__`, `inherited/scannerjson.__reduce_ex__`, `inherited/slice.__reduce_ex__`, `inherited/star.__reduce_ex__`, `inherited/struct.__reduce_ex__`, `inherited/take.__reduce_ex__`, `inherited/tee.__reduce_ex__`, `more_types/blakes.__reduce_ex__`, `more_types/grouper.__reduce_ex__`, `more_types/pargs.__reduce_ex__`, `more_types/pkwargs.__reduce_ex__`, `more_types/teedata.__reduce_ex__`, `more_types/ziplong.__reduce_ex__`, `more_types/zlibdec.__reduce_ex__`.

## A33-18 · Medium · TextIOBase.write rejects the operation before validating the argument

`runtime/prelude/_io.py:616`. Rows `io_methods/TextIOBase.{fresh,closed}.write` and `TextIOBase.fresh.writelines`. Both exit 0 with empty stderr.

```python
import io
try: io.TextIOBase().write(b'x')
except Exception as e: print(type(e).__name__)
```

CPython prints `TypeError`. Bella prints `UnsupportedOperation`. CPython's wrapper checks that the argument is text before reaching the unsupported method. Bella checks the argument count alone. IOBase.writelines dispatches to the same write method.

The same omission affects `_TextIOBase.read` and `readline` at lines 606 and 611. The additional `decoder/textbase.{read,readline}.{float,none,huge,bytes,str}` rows return UnsupportedOperation on Bella. CPython raises TypeError for the non-integers and OverflowError for `2**70`. The `textbase.write` rows confirm the text check for floats, None and integers too.

## A33-19 · Medium · IncrementalNewlineDecoder's state converter rejects indexable flags and omits overflow warnings

`runtime/prelude/_io.py:2503-2505` and `:2525-2527`. Rows `decoder/nl.{index,big,neg}.{get,set}`. Both exit 0 with empty stderr. The harness records warning categories.

```python
import io, warnings
class I:
    def __index__(self): print('index'); return 3
flag = I()
class D:
    def getstate(self): return b'',flag
    def setstate(self,p): print('state',p)
d=io.IncrementalNewlineDecoder(D(),True)
with warnings.catch_warnings(record=True) as w:
    warnings.simplefilter('always')
    try: print(d.getstate())  # set row calls d.setstate((b'',flag))
    except Exception as e: print(type(e).__name__)
    print([e.category.__name__ for e in w])
```

For get, CPython prints `index`, `(b'', 6)`, `[]`. For set, it prints `index`, `state (b'', 1)`, `None`, `[]`. Bella prints `TypeError` and `[]` for both. For either sign of `2**65`, both obtain a zero flag, but CPython records `['DeprecationWarning']` and Bella records `[]`. CPython's K converter calls the index protocol and warns when the value requires more than eight bytes. Bella requires an int instance and masks it without warning.

## A33-20 · Medium · A decoder restoring state after a failed tell sees the wrong active exception

`runtime/prelude/_io.py:3261`. Rows `decoder/restore.ok` and `decoder/restore.raise`. Both exit 0 with empty stderr. Use the A33-14 stream and codec registration with this decoder:

```python
import sys
class Dec(codecs.IncrementalDecoder):
    def decode(self,b,final=False):
        if b==b'a': raise KeyError('decode')
        return b.decode()
    def getstate(self): return b'',0
    def setstate(self,p):
        print('restore',type(sys.exception()).__name__)
        # raise ValueError('restore') in the raise row
f.read(1)
try: raise OSError
except OSError:
    try: f.tell()
    except BaseException as e: print(type(e).__name__, type(e.__context__).__name__)
```

CPython prints `restore OSError`. Bella prints `restore KeyError`. The second line agrees, `KeyError OSError` on success or `ValueError KeyError` when restore raises. CPython takes the decoding error off the pending-exception indicator, invokes setstate and then chains or restores the error. Bella calls setstate in a Python finally suite while the decoding error is handled.

## A33-21 · Medium · GenericAlias ignores the argument to __reduce_ex__

`runtime/prelude/bootstrap.py:937`. Rows `surplus/alias.{float,big,index,badindex}`. Both exit 0 with empty stderr.

```python
try: print(list[int].__reduce_ex__(1.5))
except Exception as e: print(type(e).__name__)
```

CPython prints `TypeError`. Bella prints `(<class 'types.GenericAlias'>, (<class 'list'>, (<class 'int'>,)))`. On CPython `2**60` raises OverflowError, a successful index conversion prints `index` before the result, and a raising index method prints `index` then `LookupError`. Bella prints the same reduction tuple in all four cases. Its GenericAlias override directly calls the class's reduce method. CPython's inherited object method first converts the protocol to a signed C int.

## A33-22 · Low · The lazy-import type's allocator rejects an ordinary receiver class

`runtime/src/imports.cpp:2026`. Rows `surplus/lazy.object` and `lazy.ordinary`. Both exit 0 with empty stderr.

```python
import types
try: print(type(types.LazyImportType.__new__(object)).__name__)
except Exception as e: print(type(e).__name__)
```

CPython prints `object`; an ordinary Python class prints its own name, `Ordinary`. Bella prints `TypeError` for both. CPython exposes the inherited object allocator, which can allocate the explicitly supplied class. Bella installs an unconditional rejection on the lazy-import type.

## A33-23 · Medium · BufferedRWPair refuses direct state retrieval

`runtime/prelude/_io.py:2104`. Rows `surplus/{pair,sub}.state.{fresh,filled}`. Both exit 0 with empty stderr.

```python
import io
x=io.BufferedRWPair(io.BytesIO(),io.BytesIO())
x.label='a33'
try: print(x.__getstate__())
except Exception as e: print(type(e).__name__)
```

CPython prints `{'label': 'a33'}` for the populated pair and `None` for the fresh pair, including for a subclass. Bella prints `TypeError` in all four rows. CPython inherits object's direct state retrieval. Bella installs a refusal on the pair itself. The ordinary protocol-2 reduction and copy rows still raise TypeError on both sides. The protocol-0 path is affected: in `remaining/brw.__reduce__.{fresh,closed}` CPython returns a reconstruction function and the argument tuple `(io.BufferedRWPair, object, None)`. Bella raises TypeError when copyreg calls the extra getstate method.

## A33-24 · Medium · Protocol-2 reduction misses heap types whose allocator is disabled

`runtime/src/types.cpp:3048-3052`, called from `runtime/prelude/bootstrap.py:2191`. Rows `reduced/reduce.{cmp,scanner,zlib,csv}` and `inherited/{cmp,scanner,reader,writer,compress,decompress}.__reduce_ex__`, plus `more_types/unpack.__reduce_ex__`. Both exit 0 with empty stderr.

```python
import csv
o=csv.reader([])
try: print(o.__reduce_ex__(2)[2:])
except Exception as e: print(type(e).__name__)
```

CPython prints `TypeError`; Bella prints `(None, None, None)`. These types have CPython's DISALLOW_INSTANTIATION flag, which sets tp_new to NULL. CPython's `reduce_newobj` therefore refuses before inspecting instance state. Bella's `_bella_no_tp_new` walks past CPython heap types as inheriting an allocator and misses this flag. That is an earlier and distinct failure from A33-17 on constructible types.

## A33-25 · Medium · A codec exception's notes descriptor observes the exception being annotated

`runtime/prelude/_codecs.py:205`. Rows `notes/codec.encode`, `codec.decode` and `str`. Both exit 0 with empty stderr.

```python
import codecs, sys
notes=[]
class S(str): pass
class E(Exception):
    @property
    def __notes__(self):
        print('notes',type(sys.exception()).__name__)
        return notes
def fn(v,errors):
    print('codec',type(v).__name__,type(errors).__name__,type(sys.exception()).__name__)
    raise E()
codecs.register(lambda n:codecs.CodecInfo(fn,fn,name=n))
try: raise LookupError
except LookupError:
    try: codecs.encode(S('x'),S('notes33'),S('abc'))
    except Exception as e: print(type(e).__name__,type(e.__context__).__name__,notes)
```

CPython stdout:

```text
codec S str LookupError
notes LookupError
E LookupError ["encoding with 'notes33' codec failed"]
```

Bella prints `notes E` on the middle line. The decode row gives the same distinction with a decoding note. The prelude adds the note inside its handler for E. CPython adds it while E is pending and the caller's LookupError is still the handled exception.

## A33-26 · Medium · A repr result's reflected addition can replace a JSON note or an unraisable report

`runtime/prelude/_json.py:552`, `runtime/prelude/_io.py:397`, `runtime/prelude/atexit.py:45`. Rows `reprtext/json`, `file` and `atexit`. Both exit 0 with empty stderr.

```python
import json
class Repr(str):
    def __radd__(self,left): print('radd'); return 'wrong report'
class Key(str):
    def __repr__(self): return Repr('key')
try: json.dumps({Key('k'):object()})
except Exception as e: print(type(e).__name__,e.__notes__)
```

CPython prints `TypeError ['when serializing dict item key']`. Bella prints `radd` and `TypeError ['wrong report']`. The other two rows give a file or callback a repr returning `Repr('shown')` and print the unraisable arguments. CPython prints `ValueError Exception ignored while finalizing file shown True` or `ValueError Exception ignored in atexit callback shown True`. Bella prints `radd` then `ValueError wrong report True`. The three preludes concatenate a plain prefix with the result of repr using Python addition. CPython's C formatting consumes the repr result's characters. The native deallocator and weak-reference callback controls in the same suite agree.

## A33-27 · Medium · An unraisable report loses the bound method name when a classmethod wraps a callable instance

`runtime/src/ops.cpp:1036`, reached from `runtime/src/call.cpp:2733`. Rows `finalizers/class.{ok,bad,non,recursive}`. Both exit 0 with empty stderr.

```python
import sys
class Call:
    def __call__(self,*a): raise ValueError('field')
class X: __del__=classmethod(Call())
def hook(e):
    print(e.exc_type.__name__,e.exc_value,e.exc_traceback is None,e.err_msg,e.object is None)
sys.unraisablehook=hook
x=X()
del x
```

CPython prints `ValueError field False Exception ignored while calling deallocator <bound method ? of <class '__main__.X'>> True`. Bella prints `ValueError field False None True`. CPython's method repr uses a placeholder when the wrapped callable has no name. Bella fetches its `__qualname__` unconditionally. That AttributeError reaches the unraisable formatter, which discards the message. Changing the callable's own repr does not affect the result.

## Checks that agreed

- All 320 `matrix/text.*` rows agreed byte for byte. They used each of the five newline settings, exact, subclass, empty and non-string decoder output, and both valid and malformed decoder state. The operations included full and sized reads, limited and unlimited readline, iteration, readlines, seek to start or end, tell/seek, write followed by read, truncate and detach. The 70 additional `lines` rows also agreed. These capped raw reads at two bytes, inspected each yielded or returned line individually, logged subclass method calls, and compared subclass results with the actual decoder outputs. The newline history and both buffering flags agreed.
- All 240 `matrix/io.*` rows agreed on the tested calls to eight concrete stream classes in fresh and closed states. They included FileIO.readlines, BufferedWriter.readline, StringIO.detach, BytesIO.fileno and the inherited seek, tell, truncate, fileno, iteration, context manager and writelines methods on BufferedRWPair. The `io_methods` suite also exercised the four bases and additional inherited operations. The `raw` rows used None, bool, an int subclass, float, negative, oversized and raising callback results. A reader refusing readability, a writer refusing writability, and direct fileno and isatty forwarding agreed in the corresponding rows.
- All 48 `library/re.*` rows agreed, including expand, sub and subn on text and binary patterns, a bytearray template, subclass templates, callable replacements, missing names and invalid group numbers. The named-group mapping and groupdict controls agreed. All 64 `base` rows, 52 `library/bin.*` rows and 30 `hex` rows agreed, as did both equal-alphabet cache traces in `detail/cache.*`.
- All 80 `edges/time.*` rows agreed for a struct_time constructed with a dict subclass overriding get, item lookup, containment and length. They passed combinations of strings, integers, floats and None for the two extra fields to strftime, asctime, mktime, localtime and gmtime. A separate 80-row sweep with an unexpected dict key reached the same constructor TypeError and status 1 before those operations.
- JSON agreed for the tested invalid keys and values, raising dict.items and list iterators, circular containers, incomparable sort keys, skipkeys, a float subclass with a raising repr, and an integer over the digit limit. The deep and unchecked-circular controls agreed on exception class and presence of notes. Custom codec registry lookups and the open-time decoder factory's received error argument, active exception and failure notes agreed in the controls.
- The `members/*.release` rows agreed on mid-program finalization and on identity of the original slot declaration. The dict-declared member's documentation, private name, and base-slot release order agreed. The slot validation rows agreed on the precedence of an invalid identifier or non-string over a variable conflict. Ordinary and subclassed GenericAlias copy, deepcopy and valid protocol-2 reduction agreed. Constructors overriding only init agreed for the six io types in A33-04.
- Explicit generator close, dropping a generator that raises during close, and dropping one that yields during GeneratorExit agreed on exception class and hook fields after accounting for addresses. The ordinary classmethod, staticmethod, already-bound method, property, custom binding descriptor and failed binding controls agreed. Native deallocator and weakref callbacks agreed when repr released another object. A raising signal handler delivered KeyError to the interrupted program on both sides. Printing at exit to closed stdout, a raising excepthook, and the failing shutdown-flush row agreed on the exception lines and status.
- The inherited-method suites used fresh representative objects across the requested module families. For repr, str, hash and dir the broad sweep compared successful result types or exception classes. Focused rows captured concrete values, subclass identities, and state or reduction shapes. Unsupported facilities and the documented deviations limit coverage. The probe programs record the arguments used for each call.
