Codex `gpt-6.2-astra` at low reasoning effort, 2026-11-23. Verbatim. Tag A42 in the review log. Range `d5927f0..4cbedcc`:
the steps since A41 in one review (the author's rule of 2026-11-22), of which two change what programs do: a bytes-like
argument held as a buffer from its parsing to the call's end (`78e66f1`, RL-702, RL-583) and a frame's values kept by its
frame object (`4cbedcc`, RL-222). Run non-interactively (standard input closed) in its own worktree (`bella-r42`), the
prompt worded as conformance. Probes (`r42-probes/codex/`) stayed in that worktree; the session ran all 74 rows again in
the main repository before any verdict and got the same outputs byte for byte (review log, A42).

---

# A42 · Bella conformance review

Range `d5927f0..4cbedcc`, tested at `4cbedcc` against CPython 3.15.2. Each row has a fresh process on each side. Commands below run from the checkout root.

```sh
ulimit -v 8000000
export PYTHONHASHSEED=0
p=r42-probes/codex/$suite/prog.py
bin=$(timeout 600 ./r42-build "$p")
timeout 120 .venv/bin/python "$p" "$row"
timeout 120 "$bin" "$row"
```

Each finding gives the suite and row names. The corresponding directories contain the exact program and per-row stdout, stderr and status files. All reported findings exit with status 0 on both sides. Stderr is empty unless explicitly shown.

## A42-01 · High · A generator that finishes can keep its last resumer alive

`runtime/src/core.cpp:1372` passes `f.caller` to `take_ownership` when a resume returns or unwinds. CPython's `clear_gen_frame` in `Python/ceval.c` clears `frame->previous` before transferring ownership. Consequently an exception retained from an earlier yield can delay the destruction of unrelated resources in the last resumer and its callers.

Minimal shape of [frames/prog.py](r42-probes/codex/frames/prog.py), row `finish`:

```python
held = []
class T:
    def __init__(self, tag): self.tag = tag
    def __del__(self): print("drop", self.tag)
def gen():
    x = T("gen")
    try: raise ValueError()
    except ValueError as e: held.append(e)
    yield 1
    yield 2
def resume(it):
    y = T("resumer")
    list(it)
it = gen()
next(it)
resume(it)
print("returned")
del it
held.clear()
print("done")
```

| Rows in suite `frames` | CPython stdout, successive lines | Bella stdout, successive lines |
|---|---|---|
| `finish`, `escape`, `throw` | drop resumer / returned / drop gen / done | returned / drop gen / drop resumer / done |
| `suspended` | 2 / drop resumer / returned / drop gen / done | 2 / returned / drop gen / drop resumer / done |

The second row clears the traceback during suspension and successfully resumes on both sides. The difference arises at exhaustion.

[Ownership suite](r42-probes/codex/ownership/prog.py) also reaches the erroneous resumer link when close unwinds a suspended handler. The generator catches a second exception inside a handler, saves that second traceback, then yields inside the outer handler.

| Rows in suite `ownership` | CPython stdout, successive lines | Bella stdout, successive lines |
|---|---|---|
| `close`, `delete` | drop nested / drop error / drop caller / returned / drop a / done | drop nested / drop error / returned / drop a / drop caller / done |
| `ignoreclose` | drop nested / ignored / drop error / drop caller / returned / drop a / done | drop nested / ignored / drop error / returned / drop a / drop caller / done |
| `cyclegen` | drop nested / drop error / drop a / drop caller / returned / done | drop nested / drop a / drop error / returned / drop caller / done |

For `cyclegen` the finding concerns only the caller's lifetime across the printed `returned` boundary. The collection's internal order is outside the comparison.

## A42-02 · High · A rejected BLAKE2 constructor leaves its caller's bytearray exported

`runtime/prelude/_blake2.py:124` acquires the key, salt and person exports before entering the `try` at line 127. Failure to acquire a later argument bypasses the cleanup for every earlier one. The caller catches the expected TypeError but subsequent resizing still fails.

```python
import _blake2
b = bytearray(b"?")
try: _blake2.blake2b(key=b, salt=None)
except Exception as e: print(type(e).__name__)
try: b.append(0); print("released")
except BufferError: print("still held")
```

[Buffer suite](r42-probes/codex/buffers/prog.py), rows `key` and `salt`. The latter uses `_blake2.blake2s(salt=b, person=None)`. CPython prints `TypeError / released` on both. Bella prints `TypeError / still held`.

## A42-03 · High · Base32 and Base64 decode with the wrong ignore characters

`runtime/prelude/binascii.py:430` snapshots `ignorechars` before converting `canonical`. At line 276 the Base64 decoder reads it after that conversion. Neither takes an export of this second buffer. CPython acquires it before converting `canonical` and reads its live contents in the decoder. In one direction Bella rejects valid data, in the other it accepts invalid data.

```python
import binascii
b = bytearray(b"?")
class Flag:
    def __bool__(self):
        print("bool")
        b[0] = 33
        return False
try: print(binascii.a2b_base32(b"ME======!", ignorechars=b, canonical=Flag()))
except Exception as e: print(type(e).__name__)
b.append(0)
print("released")
```

| Rows in suite `buffers` | CPython stdout, successive lines | Bella stdout, successive lines |
|---|---|---|
| `32write` (above) | bool / b'a' / released | bool / Error / released |
| `32resize` | bool / held / Error / released | bool / Error / released |
| `64resize` | bool / held / Error / released | bool / b'a' / released |

The resize rows try `b.append(33)` and print `held` if it raises BufferError. The Base64 input is `b"!YQ=="`.

The same missing export is observable after conversion, when a bytes subclass used as the Base64 alphabet is hashed. [Conversion suite](r42-probes/codex/conversion/prog.py), row `hashresize`, tries to append to `ignorechars` in `__hash__`. CPython prints `held / held / b'a'`, Bella `free / free / b'a'`. Row `hashignore` replaces its first byte with 33 while decoding `b"YQ==!"`. CPython prints `b'a'`, Bella `Error`. Bella's copy at line 276 predates the hash callback.

## A42-04 · Medium · Base64 runs the canonical flag's code before rejecting an invalid earlier argument

`runtime/prelude/binascii.py:275` converts `canonical` before checking the type of `alphabet` or acquiring `ignorechars`. The pin's generated `Modules/clinic/binascii.c.h` checks them in signature order. Even with immutable input and no successful export of an optional buffer this invokes arbitrary user code on a rejected call.

```python
import binascii
class Flag:
    def __bool__(self): print("bool"); return False
try: binascii.a2b_base64(b"", alphabet=1, canonical=Flag())
except Exception as e: print(type(e).__name__)
```

Rows `buffers/alphabet` and `buffers/ignore` (the latter substitutes `ignorechars=1`). Including the suite's final resize check, CPython prints `TypeError / released`. Bella prints `bool / TypeError / released`.

## A42-05 · High · Collecting an unpack iterator can leave the exporter locked and raise an unraisable exception

`runtime/prelude/_struct.py:125` implements release in a separate helper's deallocator, which reads its `_source` slot. The collector can clear that slot before invoking the deallocator. CPython's `unpackiter_dealloc` releases the buffer directly. The exporter here has an independent live reference throughout collection.

```python
import gc, struct
b = bytearray(b"?")
s = struct.Struct("B")
it = s.iter_unpack(b)
del s
print(next(it))
try: b.append(42)
except BufferError: print("held")
cycle = [it]
cycle.append(cycle)
del cycle, it
gc.collect()
try: b.append(0); print("released")
except BufferError: print("still held")
```

Row `buffers/iterator`. CPython stdout is `(63,) / held / released`, stderr empty. Bella stdout is `(63,) / held / still held`. Bella's [recorded stderr](r42-probes/codex/buffers/iterator/b.err) follows.

```text
Exception ignored while calling deallocator <function _BufferHold.__del__ at 0x99441d0>:
Traceback (most recent call last):
  File "/home/nathan/workspaces/nth/bella-r42/r42-probes/codex/buffers/prog.py", line 36, in <module>
AttributeError: '_BufferHold' object has no attribute '_source'
```

## A42-06 · Medium · A finaliser formatting a traceback during clear loses a still-live local's suggestion

`runtime/src/call.cpp:2608` moves the whole vector of locals out of the frame before releasing the first local. CPython's `frame_tp_clear` clears individual slots in reverse order. When the observer's finaliser runs, the earlier local `quantity` still occupies its slot in CPython. This concerns the result of `traceback.format_exception` inside the program.

```python
import traceback
class Observer:
    def __del__(self):
        print(traceback.format_exception(held)[-1].strip())
def make():
    quantity = 123
    o = Observer()
    try: quantty
    except NameError as e: return e
held = make()
traceback.clear_frames(held.__traceback__)
print(traceback.format_exception(held)[-1].strip())
```

Row `edges/clearing`. CPython stdout:

```text
NameError: name 'quantty' is not defined. Did you mean: 'quantity'?
NameError: name 'quantty' is not defined
```

Bella prints the second line twice.

Row `ownership/reenter` shows the same cause without formatting an exception. The earlier local prints `drop a` in its finaliser. The later local's finaliser prints `again`, calls `traceback.clear_frames` on the same traceback a second time, and prints `back`. CPython prints `again / drop a / back / returned / done`. Bella prints `again / back / drop a / returned / done`. On the recursive call Bella sees an empty vector, so it defers the earlier local's finaliser until the outer call resumes.

## A42-07 · Medium · Exhausting an unpack iterator releases the buffer before the Struct's weakref callback

`runtime/prelude/_struct.py:652` holds the Struct in local `s` across the exhaustion branch. Clearing `self._struct` therefore cannot destroy it until after `self._hold` has gone. CPython's `unpackiter_iternext` clears its Struct before `PyBuffer_Release`. No collection is involved.

```python
import struct, weakref
b = bytearray(b"xx")
def gone(r):
    try: b.append(42); print("free")
    except BufferError: print("held")
s = struct.Struct("B")
r = weakref.ref(s, gone)
it = s.iter_unpack(b)
del s
print(list(it))
```

Row `edges/struct`. CPython prints `held / [(120,), (120,)]`. Bella prints `free / [(120,), (120,)]`.

## A42-08 · Medium · Base32 checks alphabet length before finishing argument conversion

`runtime/prelude/binascii.py:429` builds the reverse table immediately after checking the alphabet's type. CPython's argument parser checks that it is bytes, acquires `ignorechars`, and converts `canonical`. The implementation then validates the alphabet's length. An invalid alphabet length can thus suppress a callback or mask the TypeError from a later argument.

```python
import binascii
class Flag:
    def __bool__(self): print("flag"); return False
try: binascii.a2b_base32(b"", alphabet=b"x", ignorechars=b"", canonical=Flag())
except Exception as e: print(type(e).__name__)
```

| Rows in suite `edges` | CPython stdout, successive lines | Bella stdout |
|---|---|---|
| `b32len` (above) | flag / ValueError | ValueError |
| `b32invalid` (pass `ignorechars=1`) | TypeError | ValueError |

## A42-09 · High · Base64 can silently decode stale input when a custom alphabet is hashed

`runtime/prelude/binascii.py:277` copies the primary data before the reverse-table cache lookup on line 282. The hash method can still overwrite the exported buffer. CPython obtains a buffer pointer, performs the lookup, and only then reads the encoded bytes through that pointer. This row leaves the input length fixed and does not modify `ignorechars`.

```python
import binascii
data = bytearray(b"YQ==")
class Alphabet(bytes):
    def __hash__(self):
        data[0] = 90
        return bytes.__hash__(self)
alphabet = Alphabet(b"ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/")
print(binascii.a2b_base64(data, alphabet=alphabet, ignorechars=bytearray(b"?")))
```

Row `conversion/hashdata`. CPython prints `b'e'` (the decoding of `ZQ==`), Bella prints `b'a'` (the decoding of `YQ==`).

## A42-10 · Medium · hexlify rejects a str separator whose length override reports one

`runtime/prelude/binascii.py:628` calls `ord(sep)` after accepting the separator's reported length. For a str subclass with two stored Latin-1 characters, this second operation raises TypeError. CPython's `_Py_strhex_bytes_with_sep` checks `PyObject_Length`, verifies the storage kind, and reads character zero. The first stored character in the probe is an ordinary, in-bounds ASCII character.

```python
import binascii
b = bytearray(b"xy")
class Sep(str):
    def __len__(self):
        b[0] = 65
        return 1
try: print(binascii.hexlify(b, Sep("ab")))
except Exception as e: print(type(e).__name__)
b.append(0)
print(bytes(b))
```

Row `separator/ab`. CPython prints `b'41a79'` and `b'Ay\x00'`. Bella prints `TypeError` and `b'Ay\x00'`. The later append succeeds on both error and success paths.

## Checks that agreed

Across nine probe programs, 74 rows ran on both sides. Of those, 48 matched byte for byte on stdout, stderr and exit status, 25 exhibited the ten findings above, and one reached a named stop. The stopped row was the staged two-namespace `exec` in `namespaces/staged`. A preliminary build also refused a literal `return` leaving a `finally` block under D-10. The supported return *through* a finally block was tested separately.

| Suite | Matching rows | What agreed |
|---|---|---|
| [frames](r42-probes/codex/frames/prog.py) | cell, close, comp, loop, recursion, revived | Release order across cells, positional and variadic arguments, recursive callers and a comprehension. Repeated raises accumulated the same entry lines. A cycle through a frame fired its weakref callback and revived one finalised object. A simple close released its resumer at return. |
| [handlers](r42-probes/codex/handlers/prog.py) | active, info, bare, explicit, cause, context, withtb, split, subgroup, derive, star, manager, stack, suppress, finaliser, weak, delegate, hint | Holding the handled exception or the exc-info tuple, bare and explicit reraises, cause and context, replacing the traceback, group operations and except-star. A manager and an ExitStack kept a traceback from exit. Suppression, throw through a yield-from delegate, a finished generator's suggestion and both unraisable hooks agreed. The hooks checked traceback lines and identity against the exception's traceback, then kept the traceback. |
| [expressions](r42-probes/codex/expressions/prog.py) | dictcomp, genexpr, genthrow, listcomp, module, return, setcomp | Traceback entries and lines from failing comprehensions, weakrefs and finalisers before and after dropping the exception, throwing into a new generator, exc-info at module scope, and return through finally. |
| [namespaces](r42-probes/codex/namespaces/prog.py) | chainclear, class, reraised | Clearing an inner traceback kept the caller alive until the traceback went. Clearing a finished class frame released the former class attribute. Reraising from another function after the first frame returned gave the same names and lines. |
| [edges](r42-probes/codex/edges/prog.py) | identity, zarray, zview | Three entries from different resumes shared one frame object. Compressor output fed to a decompressor with successive output limits and a final flush gave identical output bytes, eof, unconsumed_tail and unused_data for views and bytearrays. |
| [buffers](r42-probes/codex/buffers/prog.py) | 64write, compress, crc, itererror, max, pwrite, unpack | Post-call resize after failed conversions, invalid iterator input length and a bad descriptor. The Base64 ignore-character overwrite during canonical conversion also agreed for a fixed-length write. |
| [conversion](r42-probes/codex/conversion/prog.py) | closed, drop, viewerror | Closing the file descriptor inside offset conversion gave errno 9 and released the buffer. Dropping the caller's last stored exporter reference during CRC conversion agreed. An exception from the newline flag's length method released the memoryview export. |
| [separator](r42-probes/codex/separator/prog.py) | a | A one-character str subclass overwrote the input from its length method. Both hex results included that write, and both allowed a subsequent resize. |
