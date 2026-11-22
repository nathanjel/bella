Codex `gpt-6.2-astra` at low reasoning effort, 2026-11-22, the cross-check the author asked for after each step. Verbatim. Tag A34 in the
review log. Its range is `6bd852a..9966dbe`, run non-interactively (standard input closed) in its own worktree (`bella-r34`) at `9966dbe`: a
solid base by CPython's own account (RL-599) and the fixes of review A33 (RL-723 to RL-753), among them the text of a repr. Its probes
(`r34-probes/codex/`) stayed in that worktree. 23 findings; each was run on both sides by the session before any verdict (review log, A34).

---

# A34 · Bella at 9966dbe

**23 confirmed findings from 27 builds and 1,615 paired process runs.** 1,269 pairs matched stdout, stderr and exit status byte for byte. Bella exited 0 in 1,523 runs and reached a named stop in 92; CPython exited 0 throughout. No probe timed out. Two affect ordinary exception propagation or copying: a custom setter can replace the exception being propagated (A34-06), and copying an open StringIO raises ValueError (A34-11). A34-03 and A34-21 show why matching the returned value alone misses observable differences in decoder callbacks and finalisation order.

Compared with CPython 3.15.2, for the review of 6bd852a..9966dbe. Each row lives under `r34-probes/codex/GROUP/ROW/` with separate stdout, stderr and status for each interpreter. From this checkout, build with `timeout 600 ./r34-build r34-probes/codex/GROUP/prog.py`. Run `timeout 120 .venv/bin/python r34-probes/codex/GROUP/prog.py ROW` and `timeout 120 BINARY ROW`, where BINARY is the path printed by the build, with `PYTHONHASHSEED=0` and `ulimit -v 8000000`.

The matrices sample observable cases in all six requested areas. They do not establish exhaustive coverage of every internal C type, receiver, pending-error branch or field combination. In particular, coverage of open-time cleanup and failed TextIOWrapper initialisation is limited. Counts include retries and named stops. Each link below a finding opens its probe or a representative raw output.

## A34-01 · Medium · Formatting a negative length hint can execute the class module's equality method

`runtime/prelude/_operator.py:303`. Reproducer (group `names`, rows `hint`, `module`):

```python
import operator
class S(str):
    def __eq__(self, other): print("eq"); raise LookupError
class H:
    def __length_hint__(self): return -1
H.__module__ = S("mod")  # use None for the second row
try: operator.length_hint(H())
except Exception as e: print(type(e).__name__)
```

CPython prints `ValueError` for both. Bella prints `eq` then `LookupError` for the subclass, and `TypeError` for None. Both exit 0 with empty stderr. In Objects/abstract.c, PyObject_LengthHint raises ValueError with a %T conversion. Bella implements that conversion with Python tuple membership and string addition, both of which can raise while constructing the intended exception.

A34-01's %T problem also occurs in weak proxy repr (`formatting/modproxy`, `runtime/prelude/_weakref.py:58`): CPython prints the address-independent prefix `<weakproxy`; Bella prints `eq` then `LookupError`. Both exit 0 with empty stderr.

[Probe](r34-probes/codex/names/prog.py) · [CPython stdout](r34-probes/codex/names/hint/c.out) · [Bella stdout](r34-probes/codex/names/hint/b.out)

## A34-02 · Medium · Assigning a class name discards its str subclass

`runtime/src/types.cpp:1442` and `runtime/src/types.cpp:1431`. Run group `metadata`, row `class-__name__`.

```python
class S(str): pass
class C: pass
s = S("custom")
C.__name__ = s
print(type(C.__name__).__name__, C.__name__ is s)
```

CPython prints `S True`. Bella prints `str False`. Both exit 0 with empty stderr. CPython's type_set_name retains the assigned object. Bella copies its character data to ClassObject::name and constructs a plain str on access.

[Probe](r34-probes/codex/metadata/prog.py) · [CPython stdout](r34-probes/codex/metadata/class-__name__/c.out) · [Bella stdout](r34-probes/codex/metadata/class-__name__/b.out)

## A34-03 · Medium · TextIOWrapper.tell changes the decoder replay after a round trip

`runtime/prelude/_io.py:2737`. Group `streams`, rows `read0` through `read4`. The reproducer is [streams/prog.py](r34-probes/codex/streams/prog.py). For row `read2`, the necessary operations are the buffered-pair decoder in that file, a three-byte chunk size, `t.read(1); t.seek(t.tell()); t.read(1); t.tell()`. The first read consumes one of two decoded characters. The seek restores them from a two-byte snapshot. On the second tell, the previous ratio is still 3/2.

The following extracts the two reads from the logged program:

```python
import codecs, io
class Decoder:
    def __init__(self, errors): self.buffer = b""
    def decode(self, data, final=False):
        print("decode", data, final)
        data = self.buffer + data
        n = len(data) if final else len(data) // 2 * 2
        self.buffer = data[n:]
        return data[:n].decode("ascii")
    def getstate(self): return self.buffer, 3
    def setstate(self, state): self.buffer = state[0]
    def reset(self): self.buffer = b""
class Buf(io.BytesIO):
    def writable(self): return False
codecs.register(lambda n: codecs.CodecInfo(None, None, name=n, incrementaldecoder=Decoder))
t = io.TextIOWrapper(Buf(b"a\r\nb"), encoding="a34codec", newline="\n")
t._CHUNK_SIZE = 3
t.read(1)
t.seek(t.tell())
t.read(1)
t.tell()
```

At that second tell CPython calls `decode(b'a\r\x00', False)`, `getstate()`, and `setstate((b'', 3))` before calling `decode(b'a\r', False)`. Bella goes straight to the two-byte decode. Both produce cookie 55340232221128654850 here. The later two-byte snapshot shows the same difference for the other pair. Full, ordered stdout is saved in each row's c.out and b.out. All ten processes exit 0 with empty stderr. CPython textio.c:2949 calculates the estimate from the ratio, and the pinned build passes the snapshot's terminating NUL to the decoder in this case. Bella explicitly caps the estimate at the snapshot length. The cap was introduced in RL-347 to preserve the returned position. These rows expose the decoder callback difference that remains after that fix.

[Probe](r34-probes/codex/streams/prog.py) · [CPython stdout](r34-probes/codex/streams/read2/c.out) · [Bella stdout](r34-probes/codex/streams/read2/b.out)

## A34-04 · Medium · The default unraisable hook strips the type of the reported object's repr before writing it

`runtime/src/call.cpp:2699`. Group `hook`, representative row `normal-0-shown-plain`. In [hook/prog.py](r34-probes/codex/hook/prog.py), the reduced operation is `sys.__unraisablehook__(Args((ValueError, ValueError("v"), None, "report", Shown())))`, with Args captured by a temporary unraisable hook. Shown.__repr__ returns an S instance, where S derives from str. The stderr sink prints its argument's type and repr to stdout.

CPython's third write prints `3 S 'shown'`. Bella's prints `3 str 'shown'`. The remaining writes in this row agree, both return normally, process stderr is empty and status is 0. Python/errors.c:1492 calls PyFile_WriteObject, which hands the repr object itself to the stream's write method. Bella passes the character data into ErrSink::raw. The same third-write difference occurs with the failing exception string and the exception group, with either sink, whenever the first two writes succeed.

For A34-04 and A34-07, this is the common hook setup used by the reproductions:

```python
import sys
k = []
sys.unraisablehook = lambda args: k.append(type(args))
class D:
    def __del__(self): raise KeyError
x = D()
del x
sys.unraisablehook = sys.__unraisablehook__
Args = k[0]
```

Run this after the hook setup. Use `fallback = False` for A34-04 and `True` for A34-07.

```python
class Bad(Exception):
    def __str__(self): raise LookupError
class S(str): pass
class Shown:
    def __repr__(self): return S("shown")
class Sink:
    n = 0
    def write(self, s):
        self.n += 1
        print(self.n, type(s).__name__, repr(s))
        if fallback and self.n == 3: raise KeyError
    def flush(self): print("flush")
e = Bad() if fallback else ValueError("v")
obj = None if fallback else Shown()
old = sys.stderr
try:
    sys.stderr = Sink()
    sys.__unraisablehook__(Args((type(e), e, None, "report", obj)))
    print("returned")
finally:
    sys.stderr = old
```

[Probe](r34-probes/codex/hook/prog.py) · [CPython stdout](r34-probes/codex/hook/normal-0-shown-plain/c.out) · [Bella stdout](r34-probes/codex/hook/normal-0-shown-plain/b.out)

## A34-05 · Medium · Typing parameter reprs dispatch to the supplied name's addition operators

`runtime/prelude/_typing.py:381,460,519,675,813`. Group `typing`, rows `var`, `param`, `tuple`, `args`, `kwargs`.

```python
import typing
class S(str):
    def __radd__(self, other): print("radd"); return "other"
    def __add__(self, other): print("add"); return "other"
v = typing.TypeVar(S("V"))
a = repr(v)
print(type(a).__name__, str.__str__(a))
```

CPython prints `str ~V`; Bella prints `radd` then `str other`. ParamSpec and TypeVarTuple give the same pair of outputs. For ParamSpec.args and .kwargs, CPython prints `str V.args` and `str V.kwargs`; Bella prints `add` then `str other` for both. All return 0 with empty stderr. Objects/typevarobject.c formats Unicode name data with %U. The corresponding five Python methods concatenate the original object with a prefix or suffix.

[Probe](r34-probes/codex/typing/prog.py) · [CPython stdout](r34-probes/codex/typing/args/c.out) · [Bella stdout](r34-probes/codex/typing/args/b.out)

## A34-06 · High · Chaining a pending exception calls the exception subclass's attribute setter

`runtime/prelude/_json.py:563` and `runtime/prelude/_io.py:1901,2154,3243`. Group `cleanup`, rows `json`, `buf`, `pair`, `text`. Minimal JSON case:

```python
import json, sys
class Second(Exception):
    def __setattr__(self, n, v):
        print("set", n, type(sys.exception()).__name__)
        raise ArithmeticError
class Key(str):
    def __repr__(self): raise Second
def fail(o): raise KeyError
try: raise OSError
except OSError:
    try: json.dumps({Key("k"): object()}, default=fail)
    except BaseException as e:
        print(type(e).__name__, type(e.__context__).__name__,
              type(e.__cause__).__name__, e.__traceback__ is None)
```

CPython prints `Second KeyError NoneType False` on all four rows. Bella's JSON row prints `set __context__ OSError` then `ArithmeticError OSError NoneType False`. The buffered writer, buffered pair and text wrapper print `set __context__ Second` then `ArithmeticError Second NoneType False`. The text wrapper prints one more setter call when finalised. All return 0 with empty stderr. The IO reproductions arrange for the first close or flush to raise KeyError and the next close to raise Second. CPython's _PyErr_ChainExceptions1 sets the exception field directly. The prelude spells that operation as Python attribute assignment, allowing the program to replace the failure that escapes.

A further row for A34-06 is `edges/restore`, `runtime/prelude/_io.py:3377`. During tell replay, decode raises IndexError and setstate raises CtxError, whose attribute setter prints and raises RuntimeError. CPython prints `CtxError IndexError NoneType False`; Bella prints `setter __context__ / RuntimeError OSError NoneType False`. Both exit 0 with empty stderr.

[Probe](r34-probes/codex/cleanup/prog.py) · [CPython stdout](r34-probes/codex/cleanup/json/c.out) · [Bella stdout](r34-probes/codex/cleanup/json/b.out)

## A34-07 · Low · Fallback unraisable output combines two stderr writes

`runtime/src/call.cpp:3213`. Group `hook`, row `bad-3-none-flush`. Use the hook setup from A34-04 with `Args((Bad, Bad(), None, "report", None))`, where Bad.__str__ raises LookupError and the sink raises KeyError on its third write. These are the complete subsequent operations after the first three identical writes:

```text
CPython                         Bella
4 str 'Bad'                     4 str 'Bad'
5 str ': '                      5 str ': <exception str() failed>'
6 str '<exception str() failed>' 6 str '\n'
7 str '\n'                      flush
flush                           returned
returned
```

Both exit 0 with empty process stderr. The fallback reporter writes the separator and placeholder together in the handler for the failed string conversion. CPython writes each to the stream separately. Also observed when the fourth write fails and with the sink lacking flush. The complete hook matrix and logs are in the hook directory.

[Probe](r34-probes/codex/hook/prog.py) · [CPython stdout](r34-probes/codex/hook/bad-3-none-flush/c.out) · [Bella stdout](r34-probes/codex/hook/bad-3-none-flush/b.out)

## A34-08 · Medium · SyntaxError strips a subclass from its message's string result

`runtime/src/types.cpp:2662`. Group `exceptions`, rows `text` and `mutate`.

```python
class S(str): pass
class X:
    def __str__(self): return S("original")
a = str(SyntaxError(X()))
print(type(a).__name__, str.__str__(a))
```

CPython prints `S original`; Bella prints `str original`. Both exit 0 with empty stderr. The same difference occurs for IndentationError, TabError and _IncompleteInputError. With neither a filename nor an exact-integer line number, Objects/exceptions.c (SyntaxError_str) returns PyObject_Str's result directly. Bella extracts its text and constructs a plain str.

[Probe](r34-probes/codex/exceptions/prog.py) · [CPython stdout](r34-probes/codex/exceptions/text/c.out) · [Bella stdout](r34-probes/codex/exceptions/text/b.out)

## A34-09 · Medium · A weak reference joins the referent's name using Python addition

`runtime/prelude/_weakref.py:129`. Group `display`, rows `func`, `weak`, `module`.

```python
import weakref
class S(str):
    def __radd__(self, other): print("radd"); raise LookupError
def f(): pass
f.__name__ = S("myname")
try: print(repr(weakref.ref(f)).endswith("(myname)>"))
except Exception as e: print(type(e).__name__)
```

CPython prints `True`; Bella prints `radd` then `LookupError`. Both exit 0 with empty stderr. An instance with the same name supplied by its class reproduces it. Objects/weakrefobject.c:237 uses %U for the optional name. The prelude's string concatenation lets the name object intercept the operation. Testing the suffix makes the comparison independent of addresses.

[Probe](r34-probes/codex/display/prog.py) · [CPython stdout](r34-probes/codex/display/func/c.out) · [Bella stdout](r34-probes/codex/display/func/b.out)

## A34-10 · Low · File and text stream reprs truncate a type name by character count

`runtime/prelude/_io.py:1098,3405`. Group `display`, rows `file` and `text`.

```python
import io
T = type("é" * 70, (io.TextIOWrapper,), {})
x = T(io.BytesIO(), encoding="utf-8")
print(repr(x).count("é"))
x.close()
```

CPython prints `50`; Bella prints `70`. A FileIO subclass wrapping os.devnull gives the same outputs. All exit 0 with empty stderr. CPython's fileio.c:1203 and textio.c:3092 apply the precision in %.100s to the UTF-8 byte string. Bella slices 100 Unicode characters.

[Probe](r34-probes/codex/display/prog.py) · [CPython stdout](r34-probes/codex/display/text/c.out) · [Bella stdout](r34-probes/codex/display/text/b.out)

## A34-11 · High · copy.copy of an open StringIO raises ValueError

`runtime/prelude/_io.py:3699`. Group `reduce`, rows `17-exact`, `17-sub`, `17-slots`, `17-hooks`.

```python
import copy, io
try:
    y = copy.copy(io.StringIO("a"))
    print("copy", type(y).__name__, getattr(y, "value", None))
except Exception as e: print("copy", type(e).__name__)
```

CPython prints `copy StringIO None`; Bella prints `copy ValueError`. The plain and slotted subclass rows produce `copy C None` under CPython and the same ValueError under Bella. When a subclass supplies a dict as its state, CPython reports TypeError and Bella reports ValueError. Both sides exit 0 with empty stderr; the preceding reduction summaries agree. CPython's Modules/_io/stringio.c:908 checks only that the stream is open. The newly allocated stream is open and its state initialises it. Bella's _sio_check also requires prior initialisation, so restoring it fails before state validation.

[Probe](r34-probes/codex/reduce/prog.py) · [CPython stdout](r34-probes/codex/reduce/17-exact/c.out) · [Bella stdout](r34-probes/codex/reduce/17-exact/b.out)

## A34-12 · Medium · deque, reduce and _count_elements request an iterator twice

`runtime/prelude/_collections.py:218,221,231,234,1554,1559` and `runtime/prelude/_functools.py:451`. Group `protocols`, rows `deque`, `left0`, `left3`, `right0`, `right3`, `count`, `reduce`. Also group `callbacks`, row `deque`.

```python
from collections import deque
class I:
    n = 0
    def __iter__(self):
        self.n += 1
        if self.n > 1: raise ArithmeticError
        return self
    def __next__(self): raise StopIteration
try: print(deque(I()))
except Exception as e: print(type(e).__name__)
```

CPython prints `deque([])`; Bella prints `ArithmeticError`. The CPython extend/extendleft rows and _count_elements print `None`, and reduce with initial value 0 prints `0`. Bella prints `ArithmeticError` on every row. With a logging iterator, Bella prints one extra `iter ArithmeticError NoneType` before the first next; here ArithmeticError is the exception handled by the caller. All exit 0 with empty stderr. Each prelude obtains an iterator with iter() and then runs a for loop over it. CPython obtains the iterator once and calls its next slot directly.

[Probe](r34-probes/codex/protocols/prog.py) · [CPython stdout](r34-probes/codex/protocols/deque/c.out) · [Bella stdout](r34-probes/codex/protocols/deque/b.out)

## A34-13 · Medium · AST repr iterates sequences that CPython accesses by index

`runtime/prelude/_ast.py:69,97`. Group `protocols`, rows `astlist`, `fieldsaccess`, `fieldsmutate`.

```python
import ast
class L(list):
    def __len__(self): print("len"); return super().__len__()
    def __iter__(self): print("iter"); raise LookupError
    def __getitem__(self, i): print("item", i); return super().__getitem__(i)
try: print(repr(ast.Constant(L([1, 2, 3]))))
except Exception as e: print(type(e).__name__)
```

CPython prints `len`, `item 0`, `item 2`, then `Constant(value=[1, ..., 3], kind=None)`. Bella prints `iter` and `LookupError`. Python/Python-ast.c takes the length and indexes only the two ends. The prelude materialises the entire list. For the node's own _fields, CPython similarly captures its length and indexes each field; Bella enumerates it. When the first value's repr removes the last field from an ordinary list, CPython prints `IndexError` and Bella prints `C(a=x)`. With L as _fields, CPython prints `len / item 0 / item 1 / IndexError`; Bella prints `len / iter / LookupError` (slashes denote newlines). All exit 0 with empty stderr.

[Probe](r34-probes/codex/protocols/prog.py) · [CPython stdout](r34-probes/codex/protocols/astlist/c.out) · [Bella stdout](r34-probes/codex/protocols/astlist/b.out)

## A34-14 · Medium · AST and deque repr ask a metaclass for the type's name

`runtime/prelude/_ast.py:86` and `runtime/prelude/_collections.py:615`. Group `protocols`, rows `astname` and `dequename`.

```python
from collections import deque
class M(type):
    @property
    def __name__(self): print("name"); raise LookupError
class D(deque, metaclass=M): pass
try: print(repr(D()))
except Exception as e: print(type(e).__name__)
```

CPython prints `D([])`; Bella prints `name` and `LookupError`. An AST subclass A with empty _fields prints `A()` under CPython and produces the same two Bella lines. All exit 0 with empty stderr. The C reads the stored type name through _PyType_Name or tp_name. The Python attribute lookup invokes the metaclass descriptor.

The `formatting` group extends A34-14 to defaultdict, OrderedDict and SimpleNamespace (`dd`, `od`, `ns`; `runtime/prelude/_collections.py:846,1180`, `runtime/prelude/bootstrap.py:1300`). CPython prints `F(None, {})`, `O()` and `NS(a=shown)`, respectively. Bella prints `name` and `LookupError` on all three. For `repr(type("A.B", (collections.deque,), {})())` (row `dotted`), CPython prints `B([])` and Bella `A.B([])`: _PyType_Name takes the part after the last dot. These runs exit 0 with empty stderr.

[Probe](r34-probes/codex/protocols/prog.py) · [CPython stdout](r34-probes/codex/protocols/astname/c.out) · [Bella stdout](r34-probes/codex/protocols/astname/b.out)

## A34-15 · Medium · Namespace repr fails if an earlier value removes a later key

`runtime/prelude/bootstrap.py:1309`. Group `details`, row `mutation`.

```python
from types import SimpleNamespace
class M:
    def __repr__(self): del ns.b; return "m"
ns = SimpleNamespace(a=M(), b=2)
try: print(repr(ns))
except Exception as e: print(type(e).__name__)
```

CPython prints `namespace(a=m)`; Bella prints `KeyError`. Both snapshot the initial keys. Objects/namespaceobject.c:128 skips a key that disappeared, whereas Bella subscripts the dict. Both exit 0 with empty stderr.

[Probe](r34-probes/codex/details/prog.py) · [CPython stdout](r34-probes/codex/details/mutation/c.out) · [Bella stdout](r34-probes/codex/details/mutation/b.out)

## A34-16 · Medium · Namespace repr dispatches to overrides while reading its dictionary and keys

`runtime/prelude/bootstrap.py:1306,1308`. Group `details`, rows `dict`, `shortkey`, `nontext`. Three reduced cases (run separately inside the try/except from A34-15):

```python
class D(SimpleNamespace):
    @property
    def __dict__(self): print("dict"); raise RuntimeError
print(repr(D()))

class L(str):
    def __len__(self): print("len"); return 0
ns = SimpleNamespace()
vars(ns)[L("name")] = 1
print(repr(ns))

class X:
    @property
    def __class__(self): print("class"); return str
ns = SimpleNamespace()
vars(ns)[X()] = 1
print(repr(ns))
```

CPython prints `D()`, `namespace(name=1)` and `namespace()`. Bella prints `dict / RuntimeError`, `len / namespace()` and `class / TypeError`, respectively. All exit 0 with empty stderr. The keys are inserted directly into the dictionary. The C reads ns_dict, PyUnicode_Check and PyUnicode_GET_LENGTH; the prelude reads a Python attribute, asks isinstance and calls len.

[Probe](r34-probes/codex/details/prog.py) · [CPython stdout](r34-probes/codex/details/shortkey/c.out) · [Bella stdout](r34-probes/codex/details/shortkey/b.out)

## A34-17 · Medium · Namespace repr's recursion check calls equality

`runtime/prelude/bootstrap.py:1301`. Group `details`, row `nest`.

```python
from types import SimpleNamespace
class N(SimpleNamespace):
    def __eq__(self, other): print("eq"); raise LookupError
try: print(repr(N(a=N())))
except Exception as e: print(type(e).__name__)
```

CPython prints `N(a=N())`. Bella prints `eq` then `LookupError`. Both exit 0 with empty stderr. The C checks whether the identical object is already being represented. Python list membership also compares distinct objects.

[Probe](r34-probes/codex/details/prog.py) · [CPython stdout](r34-probes/codex/details/nest/c.out) · [Bella stdout](r34-probes/codex/details/nest/b.out)

## A34-18 · Medium · A typing constant evaluator compares the caller's format object and accepts integers outside C int

`runtime/prelude/_typing.py:202,205`. Group `details`, rows `huge` and `int`. With V from [details/prog.py](r34-probes/codex/details/prog.py), call `fn = typing.TypeVar("V", default=V()).evaluate_default`. Print the result's type name for a non-string, the value for a string, or the exception class.

* `fn(2**40)`: CPython prints `OverflowError`; Bella prints `V`.
* `fn(I(1))`, where I.__eq__ prints `eq` and returns True: CPython prints `V`; Bella prints `eq / repr / v`.

All exit 0 with empty stderr. Objects/typevarobject.c:185 parses format with "i" and compares the resulting C int. The prelude leaves instances of int subclasses in place and omits the width check.

[Probe](r34-probes/codex/details/prog.py) · [CPython stdout](r34-probes/codex/details/huge/c.out) · [Bella stdout](r34-probes/codex/details/huge/b.out)

## A34-19 · Medium · String formatting a typing default iterates a tuple subclass

`runtime/prelude/_typing.py:207`. Group `details`, row `tuple`.

```python
import typing
class T(tuple):
    def __iter__(self): print("iter"); raise LookupError
fn = typing.TypeVar("V", default=T((int, str))).evaluate_default
try: print(fn(4))
except Exception as e: print(type(e).__name__)
```

CPython prints `(int, str)`; Bella prints `iter` then `LookupError`. Both exit 0 with empty stderr. CPython reads each stored tuple item with PyTuple_GET_ITEM. A generator expression in the prelude invokes the subclass's iterator.

[Probe](r34-probes/codex/details/prog.py) · [CPython stdout](r34-probes/codex/details/tuple/c.out) · [Bella stdout](r34-probes/codex/details/tuple/b.out)

## A34-20 · Medium · A typing default with an explicit None qualname takes the repr branch

`runtime/prelude/_typing.py:150`. Group `details`, row `qual`.

```python
import typing
class V:
    def __init__(self): self.__qualname__ = None; self.__module__ = "m"
    def __repr__(self): print("repr"); return "v"
print(typing.TypeVar("V", default=V()).evaluate_default(4))
```

CPython prints `m.None`; Bella prints `repr` then `v`. Both exit 0 with empty stderr. _Py_typing_type_repr falls back when lookup of the qualname reports a missing attribute. The prelude uses None for the missing marker, which also matches the value the program supplied.

[Probe](r34-probes/codex/details/prog.py) · [CPython stdout](r34-probes/codex/details/qual/c.out) · [Bella stdout](r34-probes/codex/details/qual/b.out)

## A34-21 · Medium · AST repr keeps a temporary field alive across the Unicode writer callback

`runtime/prelude/_ast.py:99,109`. Group `lifetime`, row `ast`. The minimal arrangement is an AST subclass with `_fields=("x",)` and an x property returning a fresh Value. Value.__repr__ returns a fresh Text, a str subclass. Each callback and finaliser prints its name. The runnable definitions are in [lifetime/prog.py](r34-probes/codex/lifetime/prog.py).

CPython prints `value.repr / value.del NoneType / text.str / text.del / AST(x=printed)`. Bella prints `value.repr / text.str / text.del / value.del NoneType / AST(x=printed)`. Both exit 0 with empty stderr. Python/Python-ast.c releases the temporary field immediately after obtaining its repr and before WriteStr. Bella retains it in the local variable value through formatting. The destructor runs during the call on both sides.

The field and writer callbacks can be reduced to the following:

```python
import ast
class Text(str):
    def __str__(self): print("text.str"); return "printed"
    def __del__(self): print("text.del")
class Value:
    def __repr__(self): print("value.repr"); return Text("value")
    def __del__(self): print("value.del")
class Node(ast.AST):
    _fields = ("x",)
    @property
    def x(self): return Value()
print(repr(Node()))
```

[Probe](r34-probes/codex/lifetime/prog.py) · [CPython stdout](r34-probes/codex/lifetime/ast/c.out) · [Bella stdout](r34-probes/codex/lifetime/ast/b.out)

## A34-22 · Medium · AST repr installs its recursion guard after looking up _fields

`runtime/prelude/_ast.py:89,91,94`. Group `edges`, row `ast`.

```python
import ast
class M(type):
    entered = False
    @property
    def _fields(cls):
        print("fields")
        if not cls.entered:
            cls.entered = True
            print("nested", repr(node))
        return ()
class A(ast.AST, metaclass=M): pass
node = ast.AST.__new__(A)
print(repr(node))
```

CPython prints `fields / nested A(...) / A()`. Bella prints `fields / fields / nested A() / A()`. Both exit 0 with empty stderr. Python/Python-ast.c:5801 calls Py_ReprEnter before the _fields lookup. Bella checks the stack, then reads _fields and its length, and only pushes the node if there are fields. A callback during lookup can reenter it.

[Probe](r34-probes/codex/edges/prog.py) · [CPython stdout](r34-probes/codex/edges/ast/c.out) · [Bella stdout](r34-probes/codex/edges/ast/b.out)

## A34-23 · Medium · An explicit call to Struct.__init__ with no format succeeds

`runtime/prelude/_struct.py:440`. Group `methods`, row `Struct`; group `edges`, row `struct`.

```python
import struct
s = struct.Struct("b")
try: print(struct.Struct.__init__(s))
except TypeError: print("TypeError")
```

In the descriptor matrix CPython prints `Struct __init__ empty TypeError` and Bella prints `Struct __init__ empty NoneType`. In the isolated row under an outer OSError, CPython prints `TypeError OSError NoneType False` and Bella prints `None`. Both exit 0 with empty stderr. Modules/_struct.c:1991 distinguishes the first implicit init from a subsequent explicit call, for which the format is required. The prelude wraps its entire initializer in `if args or kwds`, so it silently returns for an empty call. Both probes use an already initialised exact Struct.

[Probe](r34-probes/codex/edges/prog.py) · [CPython stdout](r34-probes/codex/edges/struct/c.out) · [Bella stdout](r34-probes/codex/edges/struct/b.out)

## Comparisons that agreed

* **Stream positions and decoder state.** All 90 `states` rows agreed, including warning stderr and callback order. They combine six flag forms (negative, oversized, bool, int subclass, index provider and None), ordinary replay, failing decode or failing setstate, and five newline settings. All 15 `cookies` rows agreed, including signed field boundaries, nonzero EOF byte, invalid widths, float, custom index/int and int subclass. The UTF-8 and UTF-16 split-character reads, readline, iteration disabling tell, and write/read/end-seek sequences also agreed across the five newline settings.
* **Layout selection.** All 448 combinations in `layouts` and all 110 in `misc/layout` agreed on the selected base and MRO or exception class. They include three and four bases, user subclasses of C types, exception/non-exception mixes, ordinary slots, dict-only and weakref-only slots. The successful instance attribute checks, reassigning the existing bases, and explicit destruction of a slotted BytesIO-derived instance (slot value before dict value) agreed. Changing the class or replacing the bases with a different tuple reached a named stop.
* **Copy and reduction.** The 600-row `families` matrix used 150 type names with exact, derived, slotted and custom-state/constructor-argument variants. It compared construction, protocol 0/2/5 reduction summaries and copy outcomes: 590 pairs matched, six stopped by name and four reproduced A34-11. In the separate 160-row `reduce` matrix, including protocol 4, 153 pairs matched, three stopped by name and the same four StringIO cases differed. A custom __setstate__ that raises while an outer OSError is handled also agreed on context, cause and traceback presence.
* **Descriptor calls.** With copyreg included in the build closure, all 6,912 printed outcomes in `exception_slots` matched across 72 built-in exception names, including aliases, on exact and derived receivers. Separate descriptor matrices covered numeric and container types, iterator types, bound methods and descriptors, the IO classes, itertools, functools, operator, collections, struct, zlib, re, JSON, contextvars and weakref. The completed comparisons in these matrices agreed apart from A34-23. The matrices compare returned types and exception classes. The initial `slots` pass had 16 empty batches for module-qualified types; the subsequent `methods` pass uses their qualified table entries.
* **Formatting and error propagation.** All built-in exception repr/str batches with a raising or invalid conversion matched. The TypeVar infer-variance path preserved the name subclass, as did assigning a function name and qualname. Generic-alias and union repr called the custom module's str conversion in the same order. The exception-group repr callback order, bound-method name, t-string interpolation, and staticmethod/classmethod controls agreed. JSON scanner/encoder argument counts agreed. The callback rows for codec lookup, IO close/detach/exit/readlines/writelines, context run/reset, partial, lru_cache key failures, islice, regex substitution, struct packing, warnings, scandir and lock exit agreed on the observed handled exception, final exception class, context, cause and traceback presence.
* **Unraisable reports.** The two hook matrices contain 312 pairs, with and without a traceback, ordinary and grouped exceptions, a failing __str__, sinks with and without flush, an optional reported object and a one-shot failure on writes 1 through 12 or no failure. Successful complete reports without an object agreed in all three no-failure traceback controls. The logger identifies a frame write without comparing filenames. CPython source-line writes during fallback are the documented D-28 exclusion.
* **Buffered and compressed streams.** Constructor and close-time callback logs for all four buffered IO types agreed with raw streams whose readable, writable, seekable or closed lookup raised. Buffered write/flush reported matching errno and characters_written after a short count, zero or None with EBADF left by a failed os.write. The zlib rows matched for compressor and decompressor copies, copying with unconsumed input, repeated flush, operations after an error or end of stream, and refusal of subclassing.
