Codex `gpt-6.2-astra` at medium reasoning effort, 2026-11-20, asked by the author. Verbatim. Tag A23 in the review log. Its range is
`bc3f700..7a8e3f2`, run non-interactively (standard input closed) in its own worktree (`bella-r23`) at `7a8e3f2`, the day's change that gives the
state of a built-in type no name (RL-507), before that commit was pushed; its probes (`r23-probes/codex/`) stayed in that worktree.
A first run ended without a report, stopped by its provider's filter while it read the field code; this is the second, asked in the
same words but for the vocabulary. Twenty-eight findings; each was run on both sides by the session before any verdict (review log, A23).

---

# Bella conformance review A23

Compared detached revision `7a8e3f2` against CPython 3.15.2 on Linux, with `PYTHONHASHSEED=0` except where a probe specifies another seed. The review covers `bc3f700..7a8e3f2`. The probes and captured outputs are in [r23-probes/codex/](r23-probes/codex/). Output examples are stdout unless marked otherwise.

**28 findings.** A descriptor alias aborts Bella (A23-01). The private state reader and writer remain reachable from Python (A23-02). A CSV dialect subclass silently changes data in both directions (A23-03). Read-only member writes can change a callable, a generic alias, a union or the advertised size of a struct (A23-04). The final finding identifies a regression fixture that passes without reaching its target.

Each finding compares the reviewed tip with CPython. The observations include pre-existing behavior in the affected code paths. The final reproductions and their paired outcomes are in [reported.py](r23-probes/codex/reported.py) and [reported.results](r23-probes/codex/reported.results). The digit-limit and directory-input findings use separate launches.

## A23-01 · High · Reading a partial member under a second name aborts the process

**Location** `runtime/include/bella/object.hpp:1330` and `runtime/include/bella/object.hpp:948`. Compare `runtime/src/types.cpp:198`.

```python
from functools import partial
class P(partial):
    _p_phcount = partial.args
p = P(abs, -2)
print(p._p_phcount)
```

CPython prints `(-2,)`, with empty stderr and status 0. Bella prints nothing on stdout and terminates with SIGABRT (shell status 134). Its stderr is:

```text
terminate called after throwing an instance of 'std::out_of_range'
  what():  unordered_map::at
```

The descriptor still designates the base member `args`. Generic lookup recognizes a slot descriptor but indexes instance storage by the *lookup spelling*, `_p_phcount`. Its public field index has no entry at that key. The C++ map exception escapes the runtime. The direct descriptor path has the descriptor and uses its own name, but this normal attribute read takes the generic slot shortcut. Probe `private_alias.py`. An unrelated alias, `saved_args = partial.args`, produced the same abort in `alias_member.py`.

## A23-02 · High · Python code can still read the supposedly unnamed state

**Location** `runtime/src/call.cpp:3549`, `runtime/src/imports.cpp:1303`, `runtime/src/types.cpp:3067`.

```python
import functools

p = functools.partial(abs, -2)
ns = getattr(type(int | str).__setattr__, "__globals__", {})
print(hasattr(p, "_p_phcount"), "_bella_state_get" in ns)
if "_bella_state_get" in ns:
    print(ns["_bella_state_get"](p, "_p_phcount"))
```

CPython

```text
False False
```

Bella

```text
False True
0
```

The prelude’s Python globals contain the state accessors. The union setter is exposed as a Python function. Its `__globals__` exposes the reader, which retrieves the hidden cell. The shared importlib function also exposes the writer. The expression `"_bella_state_set" in _frozen_importlib._find_and_load.__globals__` was false on CPython and true on Bella (`more2.py fglobals`). Filtering module attribute lookup leaves these dictionaries accessible. Probe `visible.py exposed`.

## A23-03 · High · A dialect subclass silently changes CSV parsing and output

**Location** `runtime/prelude/_csv.py:383`, `runtime/prelude/_csv.py:517`.

```python
import _csv, io

class D(_csv.Dialect):
    delimiter = ";"
d = D(delimiter=",")
print(d.delimiter, next(_csv.reader(["a,b"], d)))
f = io.StringIO()
_csv.writer(f, d).writerow(["a","b"])
print(repr(f.getvalue()))
```

CPython

```text
; ['a', 'b']
'a,b\r\n'
```

Bella

```text
; ['a,b']
'a;b\r\n'
```

The dialect stores a comma. Both runtimes return the subclass’s semicolon for `d.delimiter`. CPython reads the stored delimiter from its `DialectObj` when parsing or writing. Bella’s parser and writer repeatedly read the public `d.delimiter` and therefore use the class attribute for the file format. Probe `cases2.py csv_dialect`.

## A23-04 · High · Read-only members can be written through the generic setter or their descriptor

**Location** `runtime/prelude/_functools.py:138`, `runtime/include/bella/object.hpp:1507`, `runtime/src/types.cpp:300`.

```python
from functools import partial
p = partial(abs, -4)
try:
    print("readonly", object.__setattr__(p, "args", (-77,)))
except AttributeError as e:
    print("readonly", type(e).__name__, str(e))
print("readonly call", p())
```

| CPython | Bella |
|---|---|
| `readonly AttributeError readonly attribute` | `readonly None` |
| `readonly call 4` | `readonly call 77` |

These are the two corresponding rows of `one.py`. CPython declares `partial.args` as a read-only struct member. Bella retains an ordinary writable slot for this public name. The check in `partial.__setattr__` catches regular assignment, but the generic setter writes straight to the slot. The subsequent call uses the replacement arguments.

The same defect affects three other types. Each row ran in a fresh process, with the exception class printed if assignment failed.

| Operation | CPython stdout | Bella stdout | Probe |
|---|---|---|---|
| `g = list[int]; object.__setattr__(g, '__origin__', tuple); print(g)` | `AttributeError` | `tuple[int]` | `cases2.py ga_ro` |
| `u = int \| str; object.__setattr__(u, '__args__', (float, bool)); print(u)` | `AttributeError` | `float \| bool` | `cases2.py union_ro` |
| `s = struct.Struct('I'); object.__setattr__(s, 'size', 1); print(s.size, len(s.pack(1)))` | `AttributeError` | `1 4` | `members2.py structro` |

The direct descriptor path also writes the cells. `functools.partial.args.__set__(p, (-9,))` and `type(g).__origin__.__set__(g, tuple)` both raised AttributeError on CPython and succeeded on Bella (`edges.py membset` and `memberga`). The affected declarations are at `runtime/prelude/bootstrap.py:858`, `runtime/prelude/bootstrap.py:1214` and `runtime/prelude/_struct.py:405`.

## A23-05 · High · A partial subclass can lose its underlying arguments during construction

**Location** `runtime/prelude/_functools.py:198`, `runtime/src/ops.cpp:1256`.

```python
import functools

try:
    class P(functools.partial):
        args = (11,)
    p = P(abs,-6)
    print(functools.partial.args.__get__(p))
except Exception as e:
    print(type(e).__name__)
```

CPython

```text
(-6,)
```

Bella

```text
AttributeError
```

CPython initializes the field in the base struct even if a subclass shadows args. Bella stores public members through object.__setattr__, which resolves the subclass attribute and writes the instance dictionary. The underlying partial.args member is left uninitialized. A read-only property in place of the class attribute can also prevent construction. Probe `edges.py getargs`.

With `args = (99,)` and `p = P(abs, -2)`, `print(p.args, p(), vars(p))` prints `(99,) 2 {}` on CPython and `(-2,) 2 {'args': (-2,)}` on Bella. Probe `cases2.py partial_shadow`.

## A23-06 · High · Shadowing GenericAlias.__origin__ with a property prevents construction

**Location** `runtime/prelude/bootstrap.py:825`, `runtime/src/ops.cpp:1256`.

```python
import types

try:
    class G(types.GenericAlias):
        @property
        def __origin__(self):
            return tuple
    g = G(list, int)
    print(g.__origin__, repr(g), type(g()))
except Exception as e:
    print(type(e).__name__)
```

CPython

```text
<class 'tuple'> list[int] <class 'list'>
```

Bella

```text
AttributeError
```

In CPython the public property can report tuple while the alias still represents and constructs list. During setup Bella assigns __origin__ through object.__setattr__, which invokes the read-only subclass property and raises. Aliases thus cannot keep a separate native origin and Python override. Probe `cases2.py ga_prop`.

## A23-07 · Medium · A second subclass’s same-named slot overwrites the first subclass’s slot

**Location** `runtime/include/bella/object.hpp:885`, `runtime/src/types.cpp:199`.

```python
import collections

class D(collections.deque):
    __slots__ = ("_a_items",)

class F(D):
    __slots__ = ("_a_items",)
o = F([2])
D._a_items.__set__(o, "D")
F._a_items.__set__(o, "F")
print(D._a_items.__get__(o), F._a_items.__get__(o), list(o))
```

CPython

```text
D F [2]
```

Bella

```text
F F [2]
```

The deque’s internal storage survives, but Bella deduplicates the two public slots by spelling across the MRO. Both saved member descriptors consequently reach the same field. CPython allocates one cell for each declaring class. Explicit descriptor calls make both values independently observable. Probe `members2.py twoslots`.

## A23-08 · Medium · Constructing a text stream calls a subclass setter for _finalizing

**Location** `runtime/prelude/_io.py:2745`, `runtime/src/ops.cpp:1231`.

```python
import io

log = []
class T(io.TextIOWrapper):
    def __setattr__(self, name, value):
        log.append(name)
        super().__setattr__(name, value)
f = T(io.BytesIO())
print(log)
f.close()
```

CPython

```text
[]
```

Bella

```text
['_finalizing']
```

Because _finalizing is a real member, state_set falls back to ordinary setattr. Bella’s initialization reaches the subclass hook before construction is complete. CPython initializes the struct member directly. The buffered wrapper exhibits the same issue when the subclass supplies a read-only property (members2.py streamprop). Probe `cases2.py boolhook`.

## A23-09 · Medium · Stream _finalizing accepts non-booleans and can be deleted

**Location** `runtime/prelude/_io.py:1030`, `runtime/prelude/_io.py:1036`, `runtime/prelude/_io.py:2714`.

```python
import io, os

for f in (io.TextIOWrapper(io.BytesIO()), io.BufferedWriter(io.BytesIO()), io.FileIO(os.devnull)):
    try:
        f._finalizing = 1
        print(repr(f._finalizing))
    except Exception as e:
        print(type(e).__name__)
    f.close()
```

CPython

```text
TypeError
TypeError
TypeError
```

Bella

```text
1
1
True
```

CPython defines these members as `Py_T_BOOL`, which accepts only `True` and `False`. Bella uses ordinary object slots in the text and buffered wrappers and truth-tests the value in FileIO. In a separate run deleting TextIOWrapper._finalizing raised TypeError on CPython and succeeded on Bella (cases2.py booldel). Probe `cases2.py namedbool`.

## A23-10 · Medium · GenericAlias and its iterator publish hidden field names through __slots__

**Location** `runtime/src/types.cpp:2870`, `runtime/src/types.cpp:2874`.

```python
import types
cls = type(iter(list[int]))
print(getattr(cls, "__slots__", None), "__static_attributes__" in vars(cls))
print(getattr(types.GenericAlias, "__slots__", None))
```

CPython

```text
None False
None
```

Bella

```text
('_ga_obj',) True
('__origin__', '__args__', '__unpacked__', '_ga_parameters')
```

Bootstrap calls `note_prelude_class` and `present_methods` for these types and skips `forget_python_origin`. Removing the slot descriptors leaves the original `__slots__` tuple and class metadata in place. The sweep’s `private()` filter excludes names that start and end in double underscores. It skips the `__slots__` entry that reveals `_ga_obj` and `_ga_parameters` (`pipeline/tests/test_state_without_names.py:30`). Probe `visible.py framemeta`.

This metadata also changes serialization. `print(object.__getstate__(list[int]))` prints `None` on CPython and `(None, {'__origin__': <class 'list'>, '__args__': (<class 'int'>,), '__unpacked__': False})` on Bella. The default state routine at `runtime/prelude/bootstrap.py:2162` uses the published slot names and serializes the three readable members. Probe `members2.py ga_state`.

## A23-11 · Medium · A user can construct an uninitialized generic-alias iterator

**Location** `runtime/src/types.cpp:2873`.

```python
try:
    t = type(iter(list[int]))
    x = t()
    print(type(x).__name__)
except Exception as e:
    print(type(e).__name__)
```

CPython

```text
TypeError
```

Bella

```text
generic_alias_iterator
```

CPython disallows direct creation of this iterator type. Bella sets `final_type` and omits `disallow_instantiation` when registering it. On Bella, `t()` and `object.__new__(t)` both create a raw instance (`cases2.py rawnew`). Probe `more2.py newit`.

Calling `next(object.__new__(type(iter(list[int]))))` on CPython raises TypeError during allocation. On Bella the allocation succeeds, then next raises AttributeError whose `.name` is the private spelling `_ga_obj`. Probe `roundtrip.py badread`.

## A23-12 · Medium · A partial subclass cannot assign its own shadowing attribute

**Location** `runtime/prelude/_functools.py:211`.

```python
import functools

try:
    class P(functools.partial):
        args = (22,)
    p = P(abs,-5)
    p.args = "value"
    print(p.args, p())
except Exception as e:
    print(type(e).__name__)
```

CPython

```text
value 5
```

Bella

```text
AttributeError
```

The setter rejects the literal name args before resolving the descriptor on the actual type. CPython lets the subclass instance set its own args and continues calling the partial with the original arguments. Probe `edges.py subclassset`.

## A23-13 · Medium · Restoring BytesIO state replaces and aliases the instance dictionary

**Location** `runtime/prelude/_io.py:2294`.

```python
import io

b = io.BytesIO()
b.first = 1
state = {'second':2}
b.__setstate__((b"x",0,state))
print(vars(b), vars(b) is state)
```

CPython

```text
{'first': 1, 'second': 2} False
```

Bella

```text
{'second': 2} True
```

CPython merges the supplied mapping into the existing instance dictionary. Bella installs the supplied dictionary itself, discarding earlier attributes and making later mutations of the caller’s dictionary visible on the stream. Probe `more2.py dictupdate`.

StringIO’s assignment at `runtime/prelude/_io.py:3448` has the same effect. With the same dictionaries, the measured identities and contents matched the BytesIO example on each implementation (`roundtrip.py streamdict`).

## A23-14 · Medium · BytesIO.__getstate__ loses the distinction between an absent and an allocated empty dictionary

**Location** `runtime/prelude/_io.py:2274`.

```python
import io

b = io.BytesIO(b'a')
print(b.__getstate__())
vars(b)
print(b.__getstate__())
```

CPython

```text
(b'a', 0, None)
(b'a', 0, {})
```

Bella

```text
(b'a', 0, None)
(b'a', 0, None)
```

Asking for vars(b) allocates an instance dictionary. CPython includes its empty copy in subsequent state. Bella’s state routine tests dictionary length and translates an allocated empty dictionary to None. Probe `more2.py biostate`.

The same discrepancy was measured for StringIO (`runtime/prelude/_io.py:3426`, `roundtrip.py streamdict`). The lookup also consults subclasses. A BytesIO subclass defining `__dict__ = property(lambda self: {'lie': True})` returned `(b'ab', 0, {'lie': True})` from `__getstate__()` on Bella and `(b'ab', 0, None)` on CPython (`roundtrip.py fakeio`).

## A23-15 · Medium · Struct.__new__ rejects the uninitialized state

**Location** `runtime/prelude/_struct.py:415`.

```python
import struct

try:
    s = struct.Struct.__new__(struct.Struct)
    print(s.size)
except Exception as e:
    print(type(e).__name__)
```

CPython

```text
-1
```

Bella

```text
TypeError
```

For a direct call to Struct.__new__(Struct), CPython allocates an uninitialized Struct and its size is −1. Bella unconditionally requires a format argument before allocation. This uses the base type itself. Probe `edges.py struct_uninit`.

## A23-16 · Medium · Deleting a partial releases its argument before its callable

**Location** `runtime/include/bella/object.hpp:1909`, `runtime/prelude/_functools.py:138`.

```python
import functools

class Item:
    def __init__(self, name):
        self.name = name
    def __del__(self):
        print(self.name)
    def __call__(self):
        pass
p = functools.partial(Item('func'), Item('arg'), option=Item('kw'))
del p
print('done')
```

CPython

```text
func
arg
kw
done
```

Bella

```text
arg
func
kw
done
```

Bella destroys the Python slots in sorted name order, so args releases its item before func. CPython’s partial_clear clears fn, args, kw and dict in that order. Here del p releases the only references inside the running function. There is no cycle or module teardown. Probe `lifetimes.py porder`.

## A23-17 · Medium · enumerate and zip release the current item too early

**Location** `runtime/prelude/iterating.py:226`, `runtime/prelude/iterating.py:302`.

```python
class Item:
    def __init__(self, name):
        self.name = name
    def __del__(self):
        print(self.name)
it = enumerate(map(Item, ['item']))
next(it)
print('advanced')
del it
print('done')
```

CPython

```text
advanced
item
done
```

Bella

```text
item
advanced
done
```

CPython keeps a reference to its reusable result tuple inside the iterator. Bella tracks the input and index but returns a fresh tuple without retaining it. Discarding next(it) therefore runs the item’s finalizer immediately. Replacing enumerate with zip in this example produced the same two outputs (lifetimes.py ziplife). Probe `lifetimes.py enumlife`.

## A23-18 · Low · BytesIO reports the wrong size even when empty

**Location** `runtime/prelude/_io.py:2299`.

```python
import io

for buffer in (io.BytesIO(), io.BytesIO(b'ab')):
    print(buffer.__sizeof__())
```

CPython

```text
64
64
```

Bella

```text
65
67
```

BytesIO.__sizeof__ adds the length of its bytearray plus one to a fixed 64. CPython’s BytesIO counts its internal bytes allocation only when uniquely held. An empty stream and a stream initialized with a shared bytes literal both measure 64 on the reviewed platform. Probe `edges.py sizeraw`.

After writing `b'ab'` to an initially empty BytesIO, its reported size changes from 64 to 100 on CPython and from 65 to 67 on Bella. Holding the result of `b.getvalue()` then changes it back to 64 on CPython and leaves it at 67 on Bella. Probe `more2.py sizebio`.

## A23-19 · Low · BufferedReader.__sizeof__ omits subclass slots

**Location** `runtime/prelude/_io.py:1828`.

```python
import io

class B(io.BufferedReader):
    __slots__ = ("field",)
print(io.BufferedReader(io.BytesIO(), 8).__sizeof__(), B(io.BytesIO(), 8).__sizeof__())
```

CPython

```text
160 168
```

Bella

```text
160 160
```

The implementation hard-codes a 152-byte base plus the allocated buffer. CPython adds the buffer allocation to the actual type’s basic size. A subclass adding a single slot therefore reports eight more bytes on the reviewed platform. Probe `more2.py sizebuf`.

## A23-20 · Low · The newly presented formatter iterators have an extra class-dictionary entry

**Location** `runtime/src/imports.cpp:792`, `runtime/src/types.cpp:3194`.

```python
import _string

for it in (_string.formatter_parser(''),_string.formatter_field_name_split('a')[1]):
    print(type(it).__name__,vars(type(it)).get("__module__"), type(it).__module__)
```

CPython

```text
formatteriterator None builtins
fieldnameiterator None builtins
```

Bella

```text
formatteriterator builtins builtins
fieldnameiterator builtins builtins
```

CPython resolves the type’s module to builtins without an entry named __module__ in the type dictionary. Bella retains the __module__ assignment from each class body when it presents the two types added to __hidden_classes__. The single-underscore comparison in the new sweep excludes this entry. Probe `visible.py stringmod`.

## A23-21 · High · A stricter launch-time digit limit allows a module with an invalid decimal literal to execute

**Location** `pipeline/backend/cpp.py:199`, `runtime/src/bigint.cpp:443`, `runtime/src/core.cpp:401`.

Build with the default digit limit. Run the resulting binary and the corresponding Python source under `PYTHONINTMAXSTRDIGITS=640`. The three-line program in `literal.py` can be generated exactly with the following expression.

```python
"print('executed')\nvalue = " + "9" * 641 + "\nprint(value.bit_length())\n"
```

CPython exits 1 before the first print. Stdout is empty. After identifying line 2 and the literal, stderr ends with:

```text
SyntaxError: Exceeds the limit (640 digits) for integer string conversion: value has 641 digits; use sys.set_int_max_str_digits() to increase the limit - Consider hexadecimal for huge integer literals to avoid decimal conversion limits.
```

Bella exits 0 with empty stderr and prints:

```text
executed
2130
```

CPython applies the process’s limit while parsing the module. Bella had already parsed the literal at build time. Its constant loader reconstructs the integer from its value, and the executable has no source-literal check against the limit read at startup. The [source program](r23-probes/codex/literal.py), [CPython diagnostic](r23-probes/codex/literal.cp640.err) and [Bella stdout](r23-probes/codex/literal.be640) are recorded.

## A23-22 · Medium · Finalization calls flush on a replacement sys.__stdout__

**Location** `runtime/src/call.cpp:3315` and `runtime/src/call.cpp:3840`.

```python
import os
import sys
class F:
    closed = False
    def flush(self, emit=os.write):
        emit(1, b"flush\n")
sys.__stdout__ = F()
```

CPython exits 0 with empty stdout and stderr. Bella exits 0 and prints `flush` on stdout, with empty stderr. The script leaves the active `sys.stdout` alone. Bella restores it from `sys.__stdout__` during module clearing and then explicitly calls its `flush` method. At the corresponding second flush in CPython, `sys.stdout` has been cleared. Ignoring errors from the extra call still permits arbitrary user-visible side effects. Probe `exitflush.py`.

## A23-23 · Medium · Directory input produces the wrong startup diagnostic

**Location** `runtime/src/call.cpp:3765` and `runtime/src/call.cpp:3775`.

The minimal program is [empty.py](r23-probes/codex/empty.py), a zero-byte file. Build with ordinary stdin, then launch each program with an open directory as descriptor zero.

```sh
./r23-bella r23-probes/codex/empty.py
PYTHONHASHSEED=0 .venv/bin/python r23-probes/codex/empty.py < .
PYTHONHASHSEED=0 build/compiled/empty-*/empty < .
```

Both exit 1, before executing the program, with empty stdout. CPython's stderr starts with:

```text
Fatal Python error: init_sys_streams: <stdin> is a directory, cannot continue
Python runtime state: core initialized
```

Bella's stderr starts with:

```text
Fatal Python error: init_sys_streams: can't initialize sys standard streams
Python runtime state: core initialized
IsADirectoryError: [Errno 21] Is a directory: 0
```

Each then prints a blank line and the current-thread header. CPython checks whether stdin is a directory before creating the three streams (`Python/pylifecycle.c:3167`). Bella checks whether descriptor zero is valid, tries to wrap it, and reports the resulting exception through its common stream-initialization failure path. The fatal startup reason and the additional exception line are observable independently of the thread address.

## A23-24 · Medium · Newline translation bypasses a string subclass’s replace method

**Location** `runtime/prelude/_io.py:2848`.

```python
import io

class S(str):
    def replace(self, a, b):
        return "changed"
b = io.BytesIO()
w = io.TextIOWrapper(b, newline="\r\n", write_through=True)
print(w.write(S("a\n")), b.getvalue())
```

CPython

```text
2 b'changed'
```

Bella

```text
2 b'a\r\n'
```

When newline translation is active, CPython’s `TextIOWrapper.write` calls `replace` on the supplied string (Modules/_io/textio.c, _io_TextIOWrapper_write_impl). Bella explicitly calls `str.replace`. The stream writes different bytes even though both calls report the same character count. Probe `streams.py newline`.

## A23-25 · Medium · A buffered UTF-8 write releases its input before flush

**Location** `runtime/prelude/_io.py:2699`, `runtime/prelude/_io.py:2860`.

```python
import io

class S(str):
    def __del__(self):
        print("released")
w = io.TextIOWrapper(io.BytesIO(), encoding="utf-8")
w.write(S("abc"))
print("flushing")
w.flush()
```

CPython

```text
flushing
released
```

Bella

```text
released
flushing
```

For short ASCII text and an ASCII-compatible fast encoder, CPython keeps the original string among the pending writes. Bella encodes immediately and buffers the bytes. Dropping the caller’s reference therefore runs user code earlier, while the stream is still open. This happens during a normal write, without a cycle or interpreter shutdown. Probe `streams.py subclasslife`.

## A23-26 · Medium · A custom incremental encoder returning its input is rejected

**Location** `runtime/prelude/_io.py:2852`.

```python
import io, codecs

try:
    class E:
        def __init__(self, errors): pass
        def encode(self, text):
            return text
    def find(name):
        if name == "own":
            return codecs.CodecInfo(name="own", encode=None, decode=None, incrementalencoder=E, incrementaldecoder=codecs.lookup("utf-8").incrementaldecoder)
    codecs.register(find)
    b = io.BytesIO()
    w = io.TextIOWrapper(b, encoding="own", write_through=True)
    print(w.write("abc"), b.getvalue())
except Exception as e:
    print(type(e).__name__)
```

CPython

```text
3 b'abc'
```

Bella

```text
TypeError
```

CPython’s write implementation accepts an encoder result identical to the input string and buffers that string. Bella requires a bytes result unconditionally. The diagnostic rerun in `streamcheck.be` confirms that this is the check raising TypeError. Probe `streams.py fallback`.

## A23-27 · Medium · A non-string codec name can incorrectly enter fast-encoder selection

**Location** `runtime/prelude/_io.py:2684`.

```python
import codecs, io

try:
    class Label:
        @property
        def __class__(self): return str
    u = codecs.lookup('utf-8')
    def find(n):
        if n == "custom":
            return codecs.CodecInfo(name=Label(), encode=u.encode, decode=u.decode, incrementalencoder=u.incrementalencoder, incrementaldecoder=u.incrementaldecoder)
    codecs.register(find)
    b = io.BytesIO()
    w = io.TextIOWrapper(b, encoding="custom", write_through=True)
    print(w.write("hello"), b.getvalue())
except Exception as e:
    print(type(e).__name__)
```

CPython

```text
5 b'hello'
```

Bella

```text
TypeError
```

CPython tests PyUnicode_Check on codec_info.name and uses the incremental encoder when the name is another object. In Bella isinstance consults the object’s __class__ property and str.__eq__ is then applied to a non-string receiver. Bella reports `TypeError: descriptor '__eq__' requires a 'str' object but received a 'Label'` before using the working UTF-8 encoder (`codec_label.py`). Probe `edges.py fakecodec`.

## A23-28 · Medium · The RL-519 regression test exits before the first hook call

**Location** `pipeline/tests/test_review_2026_11_19.py:508` and `pipeline/tests/test_review_2026_11_19.py:674`.

```python
class Q(type):
    @property
    def __qualname__(cls):
        return 5
print("reached the hook tests")
```

CPython and Bella both exit 1 with empty stdout. Both tracebacks end at the class definition with `TypeError: type __qualname__ must be a str, not property`. The captured output from the full fixture body is in `replay.37.json`.

Type creation rejects the property in the metaclass namespace. None of the five `sys.__excepthook__` calls run, and execution never reaches the `SystemExit` case. The test compares the two outcomes after masking traceback source lines. Matching failures therefore pass even if every hook behavior the fixture was intended to exercise regresses. An assertion that the hook loop completed would make this failure visible.

## Checks that agreed

- The full C-3-76 program produced identical output on both sides (55 lines), with empty stderr and status 0. This includes a deque subclass’s private names, enumerate with a shadowing property, map with shadowing methods, weakref’s internal hash beside a user slot, and hooks for setting, deleting and missing attributes.
- Two incompatible built-in bases raised TypeError for both class statements tested. A deque subclass’s slot named `_a_items` remained separate from the deque contents. For its subclass, `object.__getstate__`, shallow copy and deep copy agreed, including shallow copy dropping the user slot. Fresh objects allocated by `deque.__new__` and `defaultdict.__new__` agreed before initialization.
- The weak-reference checks agreed for all eleven sampled objects. Computed-name access, `dir`, class dictionaries, and the exception class from `object.__setattr__` agreed on the formatter parser’s hidden text. Missing-name AttributeErrors from `object.__getattribute__` reported the same name and receiver for the tested formatter and generic-alias iterators. The TypeVar, BLAKE2, Struct and stat-result probes also hid the tested storage names and returned the same public results.
- Reducing partially consumed forward and reverse OrderedDict iterators, a deque iterator and a generic-alias iterator gave reconstructions with the same remaining values, without consuming the originals. Ordinary partial copy, reduce and keyword application agreed. The compiled pickle import and `gc.get_referents` explicitly stopped, so there is no pickle round-trip or referent-graph verdict.
- All 44 environment settings in `env.results` agreed on stdout, stderr and exit status after normalizing the native thread identifier and process name in fatal diagnostics. They cover the four numeric/flag variables and standard stream encodings, aliases, empty values, invalid encoding names and surrogate-escaped bytes. For five encodings, the empty-write, seek-to-zero and overwrite sequence produced identical bytes. A replacement active stdout received two flushes on both runtimes.
- All 41 executable fixture bodies in `pipeline/tests/test_review_2026_11_19.py` matched on stdout, stderr and exit status with traceback source lines and addresses normalized. Each body ran in its own process, selected in `replay.py` or `replay_extra.py`. The matches include the oversized range, the regular-expression signal checks, generator throw/close, strict zip, and time conversion. A23-28 explains why one of those matches does not exercise its advertised behavior.
