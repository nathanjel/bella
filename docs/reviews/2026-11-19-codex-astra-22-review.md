Codex `gpt-6.2-astra` at low reasoning effort, 2026-11-19, asked by the author. Verbatim. Tag A22 in the review log. Its range is
`3234866..bc3f700`, run non-interactively in its own worktree (`bella-r22`) at `bc3f700`, beside the Sonnet swarm S22 of the same day;
its probes (`r22-probes/codex/`) stayed in that worktree. Thirteen findings; all were reproduced on both sides by the session before
any verdict (review log, A22).

---

# Bella review A22

Reviewed `3234866..bc3f700` at detached HEAD `bc3f700`. Each runtime finding below was observed with both `.venv/bin/python` (3.15.2) and `./r22-bella`. Programs are standalone reductions of the probes. Output blocks show the affected rows on stdout unless marked stderr.

## A22-01 · High · An exception constructor can re-enter the generator receiving the throw

`runtime/src/generator.cpp:166`

Bella constructs the pending exception while the generator is still suspended. Its constructor can therefore close the generator successfully. CPython marks the frame executing before normalization. The nested close raises ValueError, which becomes the exception delivered by throw.

```python
import warnings
warnings.simplefilter("ignore")
def gen():
    yield 1
class E(Exception):
    def __init__(self): g.close()
g = gen()
next(g)
try: g.throw(E, None)
except BaseException as e: print(type(e).__name__)
```

CPython

```text
ValueError
```

Bella

```text
E
```

## A22-02 · High · A failed delegate method lookup changes generator control flow

`runtime/src/generator.cpp:190`

The same C++ catch covers looking up the delegate’s throw method and calling it. Bella injects a descriptor lookup failure into the parent, runs its handler, and abandons the child. CPython propagates a lookup failure to the caller and restores the suspended state.

```python
import warnings
warnings.simplefilter("ignore")
class Child:
    def __iter__(self): return self
    def __next__(self): return "child"
    @property
    def throw(self): raise LookupError("lookup")
def parent(child):
    try: yield from child
    except LookupError: yield "caught"
g = parent(Child())
next(g)
try: print(g.throw(ValueError, 1))
except LookupError: print("lookup escaped")
print(next(g, "ended"))
```

CPython

```text
lookup escaped
child
```

Bella

```text
caught
ended
```

## A22-03 · Medium · Delegated throw omits the parent from the live stack

`runtime/src/generator.cpp:194`

Bella calls the delegate directly without linking the suspended parent into the running frame chain. CPython temporarily installs the yield-from frame as the current frame around the call. The missing frame is observable inside a successful delegate method.

```python
import traceback, warnings
warnings.simplefilter("ignore")
class Child:
    def __iter__(self): return self
    def __next__(self): return "child"
    def throw(self, *args): return [f.name for f in traceback.extract_stack()]
def parent(child): yield from child
g = parent(Child())
next(g)
print(g.throw(ValueError, 1))
```

CPython

```text
['<module>', 'parent', 'throw']
```

Bella

```text
['<module>', 'throw']
```

## A22-04 · Medium · Struct packing leaks the conversion hook’s exception

`runtime/prelude/_struct.py:294`

The float and complex conversion handlers both catch Exception. A direct BaseException subclass bypasses the replacement. CPython’s packers translate either conversion failure into struct.error and clear the original exception.

```python
import struct
class Halt(BaseException): pass
class Bad:
    def __float__(self): raise Halt
    def __complex__(self): raise Halt
for fmt in ("d", "D"):
    try: struct.pack(fmt, Bad())
    except BaseException as e: print(type(e).__name__, str(e), e.__context__)
```

CPython

```text
error required argument is not a float None
error required argument is not a complex None
```

Bella

```text
Halt  None
Halt  None
```

## A22-05 · Medium · Complex conversion retains its temporary across conversion of the imaginary part

`runtime/src/complex.cpp:323`

After copying the real and imaginary doubles from the temporary returned by __complex__, CPython decrements its reference before processing the imaginary argument. Bella keeps the temporary in tmp until new_impl returns. The imaginary conversion can observe the delayed finalizer.

```python
import warnings
warnings.simplefilter("ignore")
class Temp(complex):
    def __del__(self): print("released")
class Real:
    def __complex__(self): return Temp(1)
class Imag:
    def __float__(self):
        print("imag")
        return 0.
print(complex(Real(),Imag()))
```

CPython

```text
released
imag
(1+0j)
```

Bella

```text
imag
released
(1+0j)
```

## A22-06 · Medium · Clearing an earlier traceback leaves its frame’s locals alive

`runtime/src/call.cpp:2364`

Both exceptions have an entry for the same function invocation. The escaping exception still owns the locals. Bella clears only the earlier entry’s empty locals vector, ignoring the shared frame link. CPython clears the shared frame and releases the resource immediately. The escaping exception and its traceback are still live during the observation.

```python
import traceback
events = []
class Resource:
    def __del__(self): events.append("closed")
previous = []
def f():
    r = Resource()
    try: raise ValueError()
    except ValueError as e: previous.append(e.__traceback__)
    raise RuntimeError()
try: f()
except RuntimeError:
    traceback.clear_frames(previous[0])
    print(events)
```

CPython

```text
['closed']
```

Bella

```text
[]
```

## A22-07 · Medium · A class attribute hides a genuine closure cell from code metadata

`pipeline/l2/resolve.py:415`

A class body can bind x in its own namespace while forwarding an outer x to a method. The resolver records that forwarded name separately as a class free variable. The new closure check tests only child.scopes, where x is local. Bella moves x from co_cellvars to co_varnames and changes locals() iteration order, although the method still reads the correct value.

```python
def f():
    x = 4
    class C:
        x = 5
        def method(self): return x
    print(list(locals()), C().method())
print(f.__code__.co_cellvars, f.__code__.co_varnames)
f()
```

CPython

```text
('x',) ('C',)
['C', 'x'] 4
```

Bella

```text
() ('x', 'C')
['x', 'C'] 4
```

## A22-08 · Medium · The C-style warning printer silently drops the source line

`runtime/prelude/_warnings.py:309`

Run this under the filename r22-probes/codex/source.py. Both programs explicitly disable the warnings module and take the fallback path. Bella indexes the filename through its Python __getitem__ hook when checking for angle brackets. The surrounding handler swallows the lookup error. CPython examines the Unicode storage directly and reads the source. Both output blocks are stderr.

```python
# source text
import _warnings, sys
sys.modules["warnings"] = None
class Path(str):
    def __getitem__(self, key):
        raise LookupError
_warnings.warn_explicit("hello", UserWarning, Path("r22-probes/codex/source.py"), 1, module="m")
```

CPython

```text
r22-probes/codex/source.py:1: UserWarning: hello
  # source text
```

Bella

```text
r22-probes/codex/source.py:1: UserWarning: hello
```

## A22-09 · Medium · Restoring a reverse iterator invokes the state’s __int__ override

`runtime/prelude/iterating.py:166`

Bella calls int(state) after checking the range. CPython’s PyLong_AsSsize_t reads the integer payload directly. The state has payload 1 but its __int__ returns 0, so Bella resumes one element too early.

```python
class State(int):
    def __int__(self): return 0
it = reversed((1, 2))
it.__setstate__(State(1))
print(next(it))
```

CPython

```text
2
```

Bella

```text
1
```

## A22-10 · Medium · Reducing a private method records the wrong attribute name

`runtime/src/types.cpp:1773`

The class name used for private-name mangling comes from ordinary getattr, which invokes the metaclass property. CPython’s PyType_GetName reads the type’s stored name. Bella’s reconstruction tuple refers to an attribute the instance does not have.

```python
class M(type):
    @property
    def __name__(cls): return "Other"
class C(metaclass=M):
    def __f(self): pass
print(C()._C__f.__reduce__()[1][1])
```

CPython

```text
_C__f
```

Bella

```text
_Other__f
```

## A22-11 · Medium · clock_gettime propagates a KeyboardInterrupt from __index__

`runtime/prelude/time.py:143`

CPython’s time_clockid_converter replaces every failed PyLong_AsInt conversion with TypeError. Bella catches only Exception in _clockid. A KeyboardInterrupt raised by the argument’s __index__ therefore reaches the caller.

```python
import time
class Bad:
    def __index__(self): raise KeyboardInterrupt()
try: time.clock_gettime(Bad())
except BaseException as e: print(type(e).__name__)
```

CPython

```text
TypeError
```

Bella

```text
KeyboardInterrupt
```

## A22-12 · Medium · A sequence error can silently end reversed iteration

`runtime/prelude/iterating.py:133`

CPython checks the actual exception type against IndexError and StopIteration. Bella uses isinstance on the exception object, which consults its __class__ property. This converts an application exception into normal iterator exhaustion.

```python
class Impostor(Exception):
    @property
    def __class__(self): return IndexError
class Seq:
    def __len__(self): return 1
    def __getitem__(self, index): raise Impostor()
try: next(reversed(Seq()))
except BaseException as e: print(type(e).__name__)
```

CPython

```text
Impostor
```

Bella

```text
StopIteration
```

## A22-13 · Low · The post-interruption decimal-conversion check always prints kept

`conformance/cases/C-7-85_signals_inside_the_runtimes_own_work.py:92`

The final operand of this conformance row has a literal False condition. It cannot exercise str(half) after interruption. The other three operands do check arithmetic. The full case was run on both runtimes and produced the row below.

```python
big = (1 << 300_000_000) - 1
half = (1 << 150_000_000) + 12345
print("the numbers afterwards:", big.bit_length(), half % 1000,
      (big >> 299_999_990) * 3, str(half)[:1] if False else "kept")
```

CPython

```text
the numbers afterwards: 300000000 721 3069 kept
```

Bella

```text
the numbers afterwards: 300000000 721 3069 kept
```

## Checked and found clean

- All four deprecated numeric return types produced the expected values and DeprecationWarning categories. A struct integer conversion, zlib.crc32, binascii.crc32 and abstract ast.expr construction also matched the warning message, filename and line. CRC start values immediately inside and outside the signed and unsigned boundaries matched for both value and warning count.

- Generator throw with a tuple subclass used its stored elements despite an overridden __iter__. Throwing a previously raised ValueError as the value retained the same traceback depth. PEP 479 supplied the original StopIteration as both cause and context, preserved its value, and started the RuntimeError traceback at the caller.

- With an outer KeyError active, struct.pack, functools.reduce and the JSON scanner produced the expected replacement classes and retained that outer exception as context.

- The complete C-7-85 signal probe matched on all 101 output lines, including interrupted regex matches, searches, products, division and decimal conversions, and the ordering of handler calls around str and repr. Empty-cell equality and ordering also matched.

- Ran the embedded programs from `test_deprecated_number_answers.py` and `test_replaced_exceptions.py` through both entry points. All 426 numeric-sweep stdout lines, all 56 replacement-exception stdout lines, and both stderr streams matched.
- Replayed C-7-89 with ordinary CPython, CPython under the harness’s D-28 import blocker, and Bella. Bella matched the simulated reference on stdout, stderr after the harness’s traceback normalization, and exit status 1.
- The C-7-88 traceback suggestion case matched CPython on all 29 stdout lines and on stderr.
