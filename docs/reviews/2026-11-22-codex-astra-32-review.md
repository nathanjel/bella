Codex `gpt-6.2-astra` at low reasoning effort, 2026-11-22, the cross-check the author asked for after each step. Verbatim. Tag A32 in the
review log. Its range is `ad307d1..f8203de`, run non-interactively (standard input closed) in its own worktree (`bella-r32`) at `f8203de`: the
five items of review A25 done on 2026-11-21 (RL-585, RL-593, RL-594, RL-597, RL-598) and the fixes of review A31, and of those the other
direction the session asked for: where a prelude now works on a plain copy of an argument's data, what CPython keeps, returns or hands on
as the object it was given. Its probes (`r32-probes/codex/`, the links below) stayed in that worktree. 24 findings; each was run on both
sides by the session before any verdict (review log, A32).

---

# A32 · Bella conformance review

**24 confirmed findings across 1,030 fresh-process comparisons.** Four have high severity. A32-04 changes compressed data, keyed hashes and file contents after an argument callback. A32-07 aborts while formatting a failed finaliser. A32-14 changes decoded bytes, and A32-23 lets a sized text read return arbitrary replacement text.

All 27 probe programs built. Of the 1,030 rows, 863 matched byte for byte, 145 exhibited the findings below, 11 reached named implementation stops, and 11 differed only in address text or observations outside the review’s finalisation scope. The matrix samples combinations of APIs, data types and callbacks. Counts refer to rows, including rows that check several operations.

Detached f8203de, range ad307d1..f8203de. Each row starts a fresh process. Paths below are relative to r32-probes/codex. For any batch and row the commands were

```bash
ulimit -v 8000000
export PYTHONHASHSEED=0
d=r32-probes/codex/$batch
timeout 600 ./r32-build "$d/prog.py" > "$d/binary"
timeout 120 .venv/bin/python "$d/prog.py" "$row"
timeout 120 "$(cat "$d/binary")" "$row"
```

Each row directory contains both stdout, stderr and status triples. Unless stated otherwise both runs exited 0 with empty stderr. Severity reflects the program-visible consequence.

## A32-01 · Low · BytesIO discards the identity of an exact bytes initializer

[Runnable row](r32-probes/codex/identity/prog.py#L331) · [Captured outputs](r32-probes/codex/identity/bytesgetvalue)

`runtime/prelude/_io.py:2169` copies the initial bytes into a bytearray. Line 2178 materializes bytes again even when returning the whole buffer. CPython shares the exact bytes in this state. Rows identity/{bytesgetvalue,bytesread,bytesreadline} each print `bytes True` under CPython and `bytes False` under Bella.

```python
import io
x = b" ".join([b"abc", b"xyz"])
y = io.BytesIO(x).getvalue()  # also read() or readline() on a fresh stream
print(type(y).__name__, y is x)
```

Rows codecargs/{bytesrec,Brec} also compare two consecutive getvalue calls, __getstate__()[0], and a full read against the first getvalue result on the same stream. CPython prints `bytes True` three times, Bella `bytes False` three times. This also occurs after a bytes subclass initializer, where the first getvalue is an exact bytes on both sides.

## A32-02 · Low · StringIO exposes its exact str initializer on a full read

[Runnable row](r32-probes/codex/identity/prog.py#L224) · [Captured outputs](r32-probes/codex/identity/strgetvalue)

`runtime/prelude/_io.py:3365` places the decoded string between two empty substrings. That can retain the original string. Line 3439 returns the stored string, and a full slice in read or readline can return it too. CPython copies the code points for this nonempty initializer. Rows identity/{strgetvalue,strread,strreadline} each print `str False` under CPython and `str True` under Bella.

```python
import io
x = " ".join(["abc", "xyz"])
y = io.StringIO(x).getvalue()  # also read() or readline() on a fresh stream
print(type(y).__name__, y is x)
```

Rows codecargs/{strrec,Srec} make the same three comparisons after exact str and str subclass initializers. CPython prints `str False` three times and Bella `str True` three times.

## A32-03 · Low · normpath returns the input object for a single ordinary component

[Runnable row](r32-probes/codex/identity/prog.py#L239) · [Captured outputs](r32-probes/codex/identity/strnormpath)

`runtime/prelude/posix.py:1395` joins a single component and prepends an empty prefix. Both operations can preserve that component's identity. CPython creates a result from the normalized path data. Rows identity/{strnormpath,bytesnormpath} print `str False` and `bytes False` under CPython, respectively, versus `str True` and `bytes True` under Bella.

```python
import os
x = " ".join(["abc", "xyz"])  # bytes row uses b" ".join([b"abc", b"xyz"])
y = os.path.normpath(x)
print(type(y).__name__, y is x)
```

### Additional A32-03 rows

Rows edges/{strsplitroot,bytessplitroot} use `y = os.path.splitroot(x)[2]` in the A32-03 program. CPython prints `str False` and `bytes False`. Bella prints `str True` and `bytes True`. The relative-path branch at `runtime/prelude/posix.py:1368` directly returns the input as the tail. Normalization also takes that branch.

## A32-04 · High · A later argument's conversion can change the bytes CPython processes

[Runnable row](r32-probes/codex/mutation/prog.py#L4) · [Captured outputs](r32-probes/codex/mutation/zcompress)

`runtime/src/call.cpp:2089` copies a bytearray when the prelude requests its bytes. A later argument's `__index__` can overwrite an existing byte before the operation reads it. CPython observes the overwrite. Bella can compute a different checksum or keyed digest and can accept compressed input CPython rejects. The program only assigns a byte at an existing index.

```python
import zlib
a = bytearray(b"abc")
class Index:
    def __index__(self):
        a[0] = 90
        return 1
i = Index()
print(zlib.decompress(zlib.compress(a, i)))
```

The affected calls take their snapshots at `runtime/prelude/zlib.py:155`, `:187`, `:388`, `:629`, `:647`, `runtime/prelude/binascii.py:517`, `:557`, `runtime/prelude/_struct.py:580`, and at `runtime/prelude/_blake2.py:107` during key conversion. Each row below is in the mutation batch. The two unpack offsets return 0, and the one-shot decompression window argument returns 15. The decompression rows initialize the array with compressed data.

| Row | CPython stdout | Bella stdout |
|---|---|---|
| zcompress | `b'Zbc'` | `b'abc'` |
| zdecomp | `raised error` | `b'test'` |
| zobj | `raised error` | `b't'` |
| zcrc | `483926404` | `887499765` |
| zadler | `37224736` | `38600999` |
| bcrc | `483926404` | `887499765` |
| bhex | `b'5a:62:63'` | `b'61:62:63'` |
| sfrom | `(b'Zb',)` | `(b'ab',)` |
| sstruct | `(b'Zb',)` | `(b'ab',)` |
| blakekey | `c4ea5d173ccf79a6b2e8716198cffeafa627466c0d524924d227d713bfb43e19bbf2da46a212db88fcccb8ac3095f19f04b9860e3e0f1f8968224c5491a093cc` | `09765d9a0b724378cfba0eb5f12c72d204a052e4125a980854a7787e76bdc48c5a8ba4d42c64ad4c4272839dc44b294c27cc334d86c14f4ad3187326569c6801` |

The reentry batch repeats the in-place overwrite from a flag’s `__bool__`, a separator’s `__len__`, and a file offset’s `__index__`. In `runtime/prelude/posix.py:2037` this changes the actual bytes written by `os.pwrite`. The file row reads back the contents of a fresh anonymous file. Additional snapshot sites include `runtime/prelude/binascii.py:230`, `:311`, `:377`, `:455`, and `runtime/prelude/_blake2.py:108`–109.

| Row | CPython stdout | Bella stdout |
|---|---|---|
| [reentry/pwrite](r32-probes/codex/reentry/pwrite) | `b'Zbc'` | `b'abc'` |
| [reentry/b32](r32-probes/codex/reentry/b32) | `b'LJRGG==='` | `b'MFRGG==='` |
| [reentry/a32](r32-probes/codex/reentry/a32) | `b'\xc9'` | `b'a'` |
| [reentry/b64](r32-probes/codex/reentry/b64) | `b'WmJj\n'` | `b'YWJj\n'` |
| [reentry/a64](r32-probes/codex/reentry/a64) | `b'e'` | `b'a'` |
| [reentry/hex](r32-probes/codex/reentry/hex) | `b'5a:62:63'` | `b'61:62:63'` |
| [reentry/blake](r32-probes/codex/reentry/blake) | `bed95bfe17ca1a8c066155fa2f8d5c24a88643b529267a0c1698f10fbb003f2f` | `605c479d6f204e3da5ce08f882b873f1f708a078aee795072befa9b621dcf523` |
| [reentry/blakep](r32-probes/codex/reentry/blakep) | `879a4b6d167910d80d110e19c9513fb09eb4010c2fd12e5d69a29d51bc14a317` | `24f774cc574acc7187a3c451173bba8938aa554c38852a3c0e38f4d57e5c8aca` |

## A32-05 · Medium · Constructing hidden struct-sequence fields looks up a matching key twice

[Runnable row](r32-probes/codex/edges/prog.py#L346) · [Captured outputs](r32-probes/codex/edges/fieldtm_zone)

`runtime/prelude/bootstrap.py:2012` checks membership and then retrieves the field through a second lookup. CPython's `Objects/structseq.c:243` calls `PyDict_GetItemStringRef` once. A user-defined key in the supplied dictionary observes both comparisons. The key here is an ordinary object.

```python
import time
class Key:
    def __hash__(self): return hash("tm_zone")
    def __eq__(self, other):
        print("eq", other)
        return other == "tm_zone"
print(time.struct_time(range(9), {Key(): 77}).tm_zone)
```

Row edges/fieldtm_zone. CPython prints `eq tm_zone` once followed by `77`. Bella prints `eq tm_zone` twice followed by `77`.

Rows edges/{fieldst_blksize,fieldf_fsid} show the same duplicated comparison and final value for os.stat_result and os.statvfs_result, respectively.

Row reentry/fieldok prints `compare` once followed by `ZONE` on CPython, and twice followed by `ZONE` on Bella.

In focused/field the key returns True only on its first comparison. CPython prints `ok`. Bella prints `raised KeyError`. Both exit 0 with empty stderr.

## A32-06 · Low · open exposes the caller's exact strings as stream attributes

[Runnable row](r32-probes/codex/exact/prog.py#L10) · [Captured outputs](r32-probes/codex/exact/stropenmode)

`runtime/prelude/_io.py:189` returns an exact str argument unchanged. Lines 3608–3617 use that conversion for open's mode, encoding and errors, and line 2866 uses it for a directly constructed TextIOWrapper's encoding. CPython constructs Python strings from the C strings in these paths, including `Modules/_io/_iomodule.c:343` for mode and `Modules/_io/textio.c:1250` for encoding. RL-694 fixed the resulting attributes' *types* for subclass inputs. These rows use dynamically constructed exact strings.

```python
import io
x = "".join(["r", "t"])
with io.open("/dev/null", x) as f:
    print(type(f.mode).__name__, f.mode is x)
```

Rows exact/{stropenmode,stropenencoding,stropenerrors,strtwencoding}. The other three check `io.open("/dev/null", encoding=x).encoding` with `ascii`, `io.open("/dev/null", errors=x).errors` with `strict`, and `io.TextIOWrapper(io.BytesIO(), encoding=x).encoding` with `utf8`. All four print `str False` under CPython and `str True` under Bella. Both implementations preserved the errors argument of a directly constructed TextIOWrapper in the companion row.

## A32-07 · High · An exception formatting a failed deallocator aborts the process

[Runnable row](r32-probes/codex/filewarnings/prog.py#L332) · [Captured outputs](r32-probes/codex/filewarnings/callbackraise)

`runtime/src/call.cpp:3238` calls `repr_of(del.get())` while reporting an exception from the bound finalizer. A second Python exception escapes that reporting path and terminates the process before the hook runs. CPython delivers the original exception to the hook with `err_msg=None` when formatting the message fails.

```python
import sys
class D:
    def __get__(self, obj, typ): return self
    def __call__(self): raise SystemExit(3)
    def __repr__(self):
        print("repr")
        raise LookupError()
class X:
    __del__ = D()
def hook(e):
    print(type(e.exc_value).__name__, e.err_msg, e.object is None)
sys.unraisablehook = hook
x = X()
del x
print("end")
```

Row filewarnings/callbackraise. CPython exits 0 with empty stderr and prints

```text
repr
SystemExit None True
end
```

Bella's captured stdout is empty. Its status is 134 (SIGABRT), and captured stderr is

```text
terminate called after throwing an instance of 'bella::PyError'
timeout: the monitored command dumped core
```

The second stderr line comes from the timeout wrapper. Both sides reached the hook and continued in the control row filewarnings/callbackclose, where the same descriptor's repr returned a string.

## A32-08 · Medium · re exposes a discarded cache lookup exception through __context__

[Runnable row](r32-probes/codex/errorstate/prog.py#L20) · [Captured outputs](r32-probes/codex/errorstate/Ssub)

At `runtime/prelude/_sre.py:273` the retry compiles the replacement inside the handler for the unhashable original template. CPython clears that TypeError before calling the compiler again (`Modules/_sre/sre.c:1194`). When the template names a nonexistent group, Bella inserts an extra TypeError between the parser’s KeyError and the user’s active ValueError.

```python
import re
class S(str): __hash__ = None
p = re.compile(".")
x = S(r"\g<bad>")
try: raise ValueError()
except ValueError:
    try: p.sub(x, "x")
    except BaseException as e:
        while e is not None:
            print(type(e).__name__, type(e.__cause__).__name__, e.__suppress_context__)
            e = e.__context__
```

| Row | CPython stdout | Bella stdout |
|---|---|---|
| [errorstate/Ssub](r32-probes/codex/errorstate/Ssub) | `IndexError NoneType True ⏎ KeyError NoneType False ⏎ ValueError NoneType False` | `IndexError NoneType True ⏎ KeyError NoneType False ⏎ TypeError NoneType False ⏎ ValueError NoneType False` |

Rows errorstate/{S,B,bytearray}{sub,subn,expand} all have the same pair of outputs. The bytes and bytearray rows use bytes patterns and strings. ⏎ marks a newline in output tables.

## A32-09 · Medium · A JSON key’s repr observes the wrong active exception

[Runnable row](r32-probes/codex/errorstate/prog.py#L108) · [Captured outputs](r32-probes/codex/errorstate/jsonstr)

At `runtime/prelude/_json.py:644` the encoder calls repr(key) to build an exception note inside its handler for a serialization failure. CPython formats the note while that failure is pending, with the caller’s outer exception still active (`Modules/_json.c:1732` and `Python/errors.c:1273`). A key can branch on the result of sys.exception() in its repr.

```python
import json, sys
class Key(str):
    def __repr__(self):
        print(type(sys.exception()).__name__)
        return "key"
x = Key("key")
try: raise LookupError()
except LookupError:
    try: json.dumps({x: object()})
    except BaseException as e:
        while e is not None:
            print(type(e).__name__, type(e.__cause__).__name__, e.__suppress_context__)
            e = e.__context__
```

| Row | CPython stdout | Bella stdout |
|---|---|---|
| [errorstate/jsonstr](r32-probes/codex/errorstate/jsonstr) | `LookupError ⏎ TypeError NoneType False ⏎ LookupError NoneType False` | `TypeError ⏎ TypeError NoneType False ⏎ LookupError NoneType False` |

Rows errorstate/{jsonint,jsonfloat} have the same outputs for int and float keys.

## A32-10 · Medium · codecs.encode and decode expose their original option objects to Python callbacks

[Runnable row](r32-probes/codex/codecargs/prog.py#L10) · [Captured outputs](r32-probes/codex/codecargs/encodesub)

At `runtime/prelude/_codecs.py:290` and `:294`, _coding_args validates the encoding and errors as C strings, discards the conversion results, and returns the original objects. The codec receives the original errors argument at line 201. CPython constructs a plain str argument from the C string. On failing paths Bella also performs Python concatenation with the original encoding name to build an exception note or lookup error. Its reflected addition can run and change the note.

```python
import codecs
class S(str): pass
class Error(str): pass
x = S("abc")
err = Error("".join(["my ", "errors"]))
def fn(v, e=""):
    print(type(v).__name__, v is x)
    print(type(e).__name__, e is err)
    return v, 1
info = codecs.CodecInfo(fn, fn, name="a32_code")
codecs.register(lambda s: info if s == "a32_code" else None)
result = codecs.encode(x, "a32_code", err)
print(type(result).__name__, result is x)
```

| Row | CPython stdout | Bella stdout |
|---|---|---|
| [codecargs/encodesub](r32-probes/codex/codecargs/encodesub) | `S True ⏎ str False ⏎ S True` | `S True ⏎ Error True ⏎ S True` |
| [codecargs/decodesub](r32-probes/codex/codecargs/decodesub) | `B True ⏎ str False ⏎ B True` | `B True ⏎ Error True ⏎ B True` |
| [codecargs/encodeexact](r32-probes/codex/codecargs/encodeexact) | `S True ⏎ str False ⏎ S True` | `S True ⏎ str True ⏎ S True` |
| [codecargs/decodeexact](r32-probes/codex/codecargs/decodeexact) | `B True ⏎ str False ⏎ B True` | `B True ⏎ str True ⏎ B True` |
| [codecargs/encodebad](r32-probes/codex/codecargs/encodebad) | `S True ⏎ str False ⏎ LookupError ["encoding with 'a32_code' codec failed"]` | `S True ⏎ Error True ⏎ radd ⏎ LookupError ["intercepted' codec failed"]` |
| [codecargs/decodebad](r32-probes/codex/codecargs/decodebad) | `B True ⏎ str False ⏎ LookupError ["decoding with 'a32_code' codec failed"]` | `B True ⏎ Error True ⏎ radd ⏎ LookupError ["intercepted' codec failed"]` |
| [codecargs/encodebadname](r32-probes/codex/codecargs/encodebadname) | `LookupError None` | `radd ⏎ LookupError None` |
| [codecargs/decodebadname](r32-probes/codex/codecargs/decodebadname) | `LookupError None` | `radd ⏎ LookupError None` |

In the bad and badname rows the supplied encoding is a str subclass whose __radd__ prints `radd` and returns `"intercepted"`. The bad rows register a codec that raises LookupError. The badname rows request an unknown name.

## A32-11 · Medium · A pattern without named groups exposes a read-only mapping

[Runnable row](r32-probes/codex/patterns/prog.py#L46) · [Captured outputs](r32-probes/codex/patterns/strplain)

At `runtime/prelude/_sre.py:373` Pattern.groupindex wraps even a newly created empty dict in MappingProxyType. CPython's `Modules/_sre/sre.c:1607` returns a fresh mutable dict when the pattern has no group index. Assigning to this temporary mapping succeeds and leaves future reads empty.

```python
import re
p = re.compile("x")
v = p.groupindex
print(type(v).__name__, v is p.groupindex)
try: v["extra"] = 7
except BaseException as e: print(type(e).__name__)
print(dict(p.groupindex))
```

| Row | CPython stdout | Bella stdout |
|---|---|---|
| [patterns/strplain](r32-probes/codex/patterns/strplain) | `dict False ⏎ {}` | `mappingproxy False ⏎ TypeError ⏎ {}` |

Rows patterns/{Splain,Bplain,bytesplain} give the same outputs. Patterns with named groups exposed a mappingproxy on both sides.

Row verify/groupmapping writes a real item into the returned mapping. CPython prints `{'foo': 1}` followed by `{}`. Bella prints `readonly` followed by `{}`.

## A32-12 · Medium · Match.groupdict hashes a named-group key an extra time

[Runnable row](r32-probes/codex/patterns/prog.py#L82) · [Captured outputs](r32-probes/codex/patterns/plain)

At `runtime/prelude/_sre.py:612` the result dict’s item assignment hashes the key again after _getindex has looked it up. CPython inserts the result with the hash already stored in the pattern’s dictionary (`Modules/_sre/sre.c:2513`). The first hash printed in this row comes from constructing the input dictionary, before groupdict runs. The supplied code is the SRE sequence for a capture around the literal x.

```python
import _sre
active = False
seen = []
class Key(str):
    def __hash__(self):
        print("hash")
        if active and not seen:
            seen.append(0)
            pass
        return str.__hash__(self)
key = Key("name")
d = {key: 1}
p = _sre.compile("x", 0, [17, 0, 16, 120, 17, 1, 1], 1, d, (None, key))
m = p.match("x")
active = True
try: print(m.groupdict())
except BaseException as e: print("raised", type(e).__name__)
```

| Row | CPython stdout | Bella stdout |
|---|---|---|
| [patterns/plain](r32-probes/codex/patterns/plain) | `hash ⏎ hash ⏎ {'name': 'x'}` | `hash ⏎ hash ⏎ hash ⏎ {'name': 'x'}` |

The verify batch counts hashes only during groupdict. The key in hashraise raises on its second hash during that call.

| Row | CPython stdout | Bella stdout |
|---|---|---|
| [verify/hash](r32-probes/codex/verify/hash) | `{'a32': 'x'} ⏎ 1` | `{'a32': 'x'} ⏎ 2` |
| [verify/keys](r32-probes/codex/verify/keys) | `{'a32': 'x'} ⏎ 1` | `{'a32': 'x'} ⏎ 2` |
| [verify/hashraise](r32-probes/codex/verify/hashraise) | `{'a32': 'x'} ⏎ 1` | `LookupError ⏎ 2` |

## A32-13 · Medium · Match.groupdict raises when a key adds a group during traversal

[Runnable row](r32-probes/codex/patterns/prog.py#L99) · [Captured outputs](r32-probes/codex/patterns/mutate)

At `runtime/prelude/_sre.py:611` groupdict traverses groupindex with a Python dict iterator. It checks for a size change on the next step. CPython traverses with _PyDict_Next (`Modules/_sre/sre.c:2504`), so it visits the newly inserted key and includes the same capture under both names in the output. This traversal difference persists independently of the redundant hash call in A32-12.

```python
import _sre
active = False
seen = []
class Key(str):
    def __hash__(self):
        print("hash")
        if active and not seen:
            seen.append(0)
            d["added"] = 1
        return str.__hash__(self)
key = Key("name")
d = {key: 1}
p = _sre.compile("x", 0, [17, 0, 16, 120, 17, 1, 1], 1, d, (None, key))
m = p.match("x")
active = True
try: print(m.groupdict())
except BaseException as e: print("raised", type(e).__name__)
```

| Row | CPython stdout | Bella stdout |
|---|---|---|
| [patterns/mutate](r32-probes/codex/patterns/mutate) | `hash ⏎ hash ⏎ {'name': 'x', 'added': 'x'}` | `hash ⏎ hash ⏎ hash ⏎ raised RuntimeError` |

With a named pattern compiled from the parser’s emitted code, the following rows add or remove an entry during the first lookup. The trailing number counts hashes during groupdict.

| Row | CPython stdout | Bella stdout |
|---|---|---|
| [verify/grow](r32-probes/codex/verify/grow) | `{'a32': 'x', 'extra': 'x'} ⏎ 1` | `RuntimeError ⏎ 2` |
| [verify/replace](r32-probes/codex/verify/replace) | `{'a32': 'x', 'extra': 'x'} ⏎ 1` | `RuntimeError ⏎ 2` |
| [verify/delete](r32-probes/codex/verify/delete) | `{'a32': 'x'} ⏎ 1` | `RuntimeError ⏎ 2` |

## A32-14 · High · binascii lets a subclass change the decoding alphabet’s size and contents

[Runnable row](r32-probes/codex/alphabets/prog.py#L69) · [Captured outputs](r32-probes/codex/alphabets/base64wrong)

At `runtime/prelude/binascii.py:198`, _reverse_table dispatches len(alphabet) to the subclass. CPython uses PyBytes_GET_SIZE in Modules/binascii.c:669. An alphabet with exactly the required bytes can therefore be rejected.

```python
import binascii
class Alphabet(bytes):
    def __len__(self): return 0
a = Alphabet(b"ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/")
try: print(binascii.a2b_base64(b"YQ==", alphabet=a))
except BaseException as e: print("raised", type(e).__name__)
```

| Row | CPython stdout | Bella stdout |
|---|---|---|
| [neighbors/base64len](r32-probes/codex/neighbors/base64len) | `b'a'` | `raised ValueError` |
| [neighbors/base32len](r32-probes/codex/neighbors/base32len) | `b'a'` | `raised ValueError` |

On a cache miss, line 204 also calls alphabet[i] for each byte. CPython reads the byte storage directly. A reversed alphabet with a subclass method that indexes in reverse demonstrates silently different decoded bytes. In the lookup rows the subclass raises on indexing. In the log rows it forwards indexing and counts calls.

```python
import binascii
class Alphabet(bytes):
    def __getitem__(self, k):
        return bytes.__getitem__(self, bytes.__len__(self) - 1 - k)
a = Alphabet(b"ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/"[::-1])
print(binascii.a2b_base64(b"YQ==", alphabet=a))
print("end", 0)
```

| Row | CPython stdout | Bella stdout |
|---|---|---|
| [alphabets/base64wrong](r32-probes/codex/alphabets/base64wrong) | `b'\x9e' ⏎ end 0` | `b'a' ⏎ end 0` |
| [alphabets/base32wrong](r32-probes/codex/alphabets/base32wrong) | `b'\x9e' ⏎ end 0` | `b'a' ⏎ end 0` |
| [alphabets/base64lookup](r32-probes/codex/alphabets/base64lookup) | `b'\x9e' ⏎ end 0` | `LookupError ⏎ end 0` |
| [alphabets/base32lookup](r32-probes/codex/alphabets/base32lookup) | `b'\x9e' ⏎ end 0` | `LookupError ⏎ end 0` |
| [alphabets/base64log](r32-probes/codex/alphabets/base64log) | `b'\x9e' ⏎ end 0` | `b'\x9e' ⏎ end 64` |
| [alphabets/base32log](r32-probes/codex/alphabets/base32log) | `b'\x9e' ⏎ end 0` | `b'\x9e' ⏎ end 32` |

## A32-15 · Medium · A prepopulated binascii alphabet cache skips an observable hash

[Runnable row](r32-probes/codex/alphabets/prog.py#L79) · [Captured outputs](r32-probes/codex/alphabets/base64raisehash)

At `runtime/prelude/binascii.py:212` and `:364`, building the default tables inserts the standard alphabets in the same dictionary that services explicit alphabet arguments. CPython has static default tables and creates an empty explicit-alphabet cache (`Modules/binascii.c:2767`). On the first explicit lookup of an equal subclass object CPython hashes for lookup and insertion. Bella finds the prepopulated entry on the first lookup.

```python
import binascii
class Alphabet(bytes):
    def __hash__(self):
        print("hash")
        return bytes.__hash__(self)
a = Alphabet(b"ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/")
print(binascii.a2b_base64(b"YQ==", alphabet=a))
```

| Row | CPython stdout | Bella stdout |
|---|---|---|
| [neighbors/base64hash](r32-probes/codex/neighbors/base64hash) | `hash ⏎ hash ⏎ b'a'` | `hash ⏎ b'a'` |
| [neighbors/base32hash](r32-probes/codex/neighbors/base32hash) | `hash ⏎ hash ⏎ b'a'` | `hash ⏎ b'a'` |

A second hash that raises makes CPython propagate ArithmeticError while Bella returns decoded data. CPython also retains the explicitly supplied key across deletion of the caller’s reference. The lifetime rows show Bella releasing the key before the `end` marker; that distinction occurs during ordinary execution.

| Row | CPython stdout | Bella stdout |
|---|---|---|
| [alphabets/base32raisehash](r32-probes/codex/alphabets/base32raisehash) | `ArithmeticError ⏎ end 2` | `b'a' ⏎ end 1` |
| [alphabets/base64raisehash](r32-probes/codex/alphabets/base64raisehash) | `ArithmeticError ⏎ end 2` | `b'a' ⏎ end 1` |
| [alphabets/base32lifetime](r32-probes/codex/alphabets/base32lifetime) | `b'a' ⏎ end 0 ⏎ released` | `b'a' ⏎ released ⏎ end 0` |
| [alphabets/base64lifetime](r32-probes/codex/alphabets/base64lifetime) | `b'a' ⏎ end 0 ⏎ released` | `b'a' ⏎ released ⏎ end 0` |

## A32-16 · Medium · IncrementalNewlineDecoder drops the subclass when returning unchanged input

[Runnable row](r32-probes/codex/neighbors/prog.py#L58) · [Captured outputs](r32-probes/codex/neighbors/dec000)

At `runtime/prelude/_io.py:2426` _nl_decode unconditionally converts a str subclass to a plain str before scanning it. CPython can scan the characters and keep the object it received. The rows vary translation, final input, and the presence of LF, CR or CRLF. Newline tracking agrees in the listed rows, while the returned object and type differ.

```python
import io
class S(str): pass
x = S("xy")
d = io.IncrementalNewlineDecoder(None, 0)
y = d.decode(x, 0)
print(type(y).__name__, y is x)
print(repr(d.newlines))
```

| Row | CPython stdout | Bella stdout |
|---|---|---|
| [neighbors/dec000](r32-probes/codex/neighbors/dec000) | `S True ⏎ None` | `str False ⏎ None` |
| [neighbors/dec001](r32-probes/codex/neighbors/dec001) | `S True ⏎ '\n'` | `str False ⏎ '\n'` |
| [neighbors/dec003](r32-probes/codex/neighbors/dec003) | `S True ⏎ '\r\n'` | `str False ⏎ '\r\n'` |
| [neighbors/dec004](r32-probes/codex/neighbors/dec004) | `S True ⏎ None` | `str False ⏎ None` |
| [neighbors/dec010](r32-probes/codex/neighbors/dec010) | `S True ⏎ None` | `str False ⏎ None` |
| [neighbors/dec011](r32-probes/codex/neighbors/dec011) | `S True ⏎ '\n'` | `str False ⏎ '\n'` |
| [neighbors/dec012](r32-probes/codex/neighbors/dec012) | `S True ⏎ '\r'` | `str False ⏎ '\r'` |
| [neighbors/dec013](r32-probes/codex/neighbors/dec013) | `S True ⏎ '\r\n'` | `str False ⏎ '\r\n'` |
| [neighbors/dec014](r32-probes/codex/neighbors/dec014) | `S True ⏎ None` | `str False ⏎ None` |
| [neighbors/dec100](r32-probes/codex/neighbors/dec100) | `S True ⏎ None` | `str False ⏎ None` |
| [neighbors/dec101](r32-probes/codex/neighbors/dec101) | `S True ⏎ '\n'` | `str False ⏎ '\n'` |
| [neighbors/dec104](r32-probes/codex/neighbors/dec104) | `S True ⏎ None` | `str False ⏎ None` |
| [neighbors/dec110](r32-probes/codex/neighbors/dec110) | `S True ⏎ None` | `str False ⏎ None` |
| [neighbors/dec111](r32-probes/codex/neighbors/dec111) | `S True ⏎ '\n'` | `str False ⏎ '\n'` |
| [neighbors/dec114](r32-probes/codex/neighbors/dec114) | `S True ⏎ None` | `str False ⏎ None` |

## A32-17 · Medium · A surrogate in struct_time.tm_zone is accepted where CPython raises

[Runnable row](r32-probes/codex/neighbors/prog.py#L214) · [Captured outputs](r32-probes/codex/neighbors/asctimeinvalid)

At `runtime/prelude/time.py:448` _gettmarg uses the surrogateescape error handler to encode tm_zone. CPython's `Modules/timemodule.c:644` uses strict PyUnicode_AsUTF8. The invalid zone gets through even for functions which do not need the zone text for their result. In the strftime row Bella actually writes the bytes FF 0A to stdout; the table uses a hexadecimal escape for FF.

```python
import time
class S(str): pass
x = time.struct_time((2024,1,3,0,0,0,1,1,-1), {"tm_zone": S(chr(0xdcff))})
try: print(time.asctime(x))
except BaseException as e: print("raised", type(e).__name__)
```

| Row | CPython stdout | Bella stdout |
|---|---|---|
| [neighbors/asctimeinvalid](r32-probes/codex/neighbors/asctimeinvalid) | `raised UnicodeEncodeError` | `Tue Jan  3 00:00:00 2024` |
| [neighbors/mktimeinvalid](r32-probes/codex/neighbors/mktimeinvalid) | `raised UnicodeEncodeError` | `1704236400.0` |
| [neighbors/strftimeinvalid](r32-probes/codex/neighbors/strftimeinvalid) | `raised UnicodeEncodeError` | `\xff` |

## A32-18 · Medium · Sized TextIOWrapper reads pass a copy of the input chunk to the decoder

[Runnable row](r32-probes/codex/streamcodec/prog.py#L172) · [Captured outputs](r32-probes/codex/streamcodec/read1charlfstr)

At `runtime/prelude/_io.py:2644` the wrapper converts the chunk returned by the buffer to an exact bytes before calling the incremental decoder. CPython measures the chunk and then passes the original object to decode (`Modules/_io/textio.c:2021`). A Python decoder can select its result based on the chunk type or identity. All 18 streamcodec rows for read(1), read(7), or readline exhibit this difference.

```python
import codecs, io
class B(bytes): pass
b = B(b"abc")
x = " ".join(["abc", "xyz"])
class Buffer(io.BytesIO):
    def writable(self): return False
    def read1(self, n=-1): return b if super().read1(n) else b""
class Dec(codecs.IncrementalDecoder):
    def decode(self, chunk, final=False):
        print(type(chunk).__name__, chunk is b)
        return x if chunk else ""
info = codecs.CodecInfo(None, None, incrementaldecoder=Dec, name="a32txt")
codecs.register(lambda n: info if n == "a32txt" else None)
f = io.TextIOWrapper(Buffer(b), encoding="a32txt", newline="\n")
y = f.read(1)
print(type(y).__name__, y is x)
print(y)
```

| Row | CPython stdout | Bella stdout |
|---|---|---|
| [streamcodec/read1charlfstr](r32-probes/codex/streamcodec/read1charlfstr) | `B True ⏎ str False ⏎ a` | `bytes False ⏎ str False ⏎ a` |
| [streamcodec/readallcharslfstr](r32-probes/codex/streamcodec/readallcharslfstr) | `B True ⏎ str True ⏎ abc xyz` | `bytes False ⏎ str True ⏎ abc xyz` |
| [streamcodec/readlinelfstr](r32-probes/codex/streamcodec/readlinelfstr) | `B True ⏎ bytes False ⏎ str True ⏎ abc xyz` | `bytes False ⏎ bytes False ⏎ str True ⏎ abc xyz` |

All affected rows are streamcodec/{read1char,readallchars,readline}{empty,lf,none}{S,str}. The first output line changes from `B True` to `bytes False` throughout. The remaining lines agree for each pair.

## A32-19 · Medium · An unbounded TextIOWrapper read rejects data its decoder accepts

[Runnable row](r32-probes/codex/focused/prog.py#L4) · [Captured outputs](r32-probes/codex/focused/arrayFalse)

At `runtime/prelude/_io.py:3006` the read-all path rejects an underlying read result unless it is bytes or a subclass. CPython special-cases None, then passes the returned object straight to the decoder (`Modules/_io/textio.c:2095`). This also affects the standard ASCII decoder, which accepts a bytearray.

```python
import io
x = bytearray(b"hello")
class Buffer(io.BytesIO):
    def read(self, *args): return x
    def writable(self): return False
f = io.TextIOWrapper(Buffer(), encoding="ascii", newline="\n")
try: print(f.read())
except BaseException as e: print("raised", type(e).__name__)
```

| Row | CPython stdout | Bella stdout |
|---|---|---|
| [focused/arrayFalse](r32-probes/codex/focused/arrayFalse) | `hello` | `raised TypeError` |
| [focused/arrayTrue](r32-probes/codex/focused/arrayTrue) | `bytearray True ⏎ done` | `raised TypeError` |
| [focused/listTrue](r32-probes/codex/focused/listTrue) | `list True ⏎ done` | `raised TypeError` |
| [focused/textTrue](r32-probes/codex/focused/textTrue) | `str True ⏎ done` | `raised TypeError` |

The True rows use a decoder that prints the argument’s type and identity and returns "done".

## A32-20 · Medium · An unbounded TextIOWrapper read loses the decoder result’s identity

[Runnable row](r32-probes/codex/streamcodec/prog.py#L46) · [Captured outputs](r32-probes/codex/streamcodec/readlfS)

At `runtime/prelude/_io.py:3009` the wrapper combines buffered text and the decoded result with Python addition. With no buffered text, CPython’s PyUnicode_AppendAndDel can hand over the actual decoded string, including its subclass. The explicit LF row isolates this operation from A32-16. With universal newline decoding A32-16 can already convert the string before this line.

```python
import codecs, io
class S(str): pass
class B(bytes): pass
x, b = S("abc xyz"), B(b"abc")
class Buffer(io.BytesIO):
    def writable(self): return False
    def read(self, n=-1): return b if super().read(n) else b""
class Dec(codecs.IncrementalDecoder):
    def decode(self, data, final=False):
        print(type(data).__name__, data is b)
        return x if data else ""
info = codecs.CodecInfo(None, None, incrementaldecoder=Dec, name="a32txt")
codecs.register(lambda n: info if n == "a32txt" else None)
f = io.TextIOWrapper(Buffer(b), encoding="a32txt", newline="\n")
y = f.read()
print(type(y).__name__, y is x)
print(y)
```

| Row | CPython stdout | Bella stdout |
|---|---|---|
| [streamcodec/readlfS](r32-probes/codex/streamcodec/readlfS) | `B True ⏎ S True ⏎ abc xyz` | `B True ⏎ str False ⏎ abc xyz` |
| [streamcodec/readnoneS](r32-probes/codex/streamcodec/readnoneS) | `B True ⏎ S True ⏎ abc xyz` | `B True ⏎ str False ⏎ abc xyz` |
| [streamcodec/reademptyS](r32-probes/codex/streamcodec/reademptyS) | `B True ⏎ S True ⏎ abc xyz` | `B True ⏎ str False ⏎ abc xyz` |

The same addition can change the actual text. In streamdetail/readbytes the decoder returns a str subclass whose __radd__ prints `radd` and returns `"changed"`. CPython returns the decoded text.

| Row | CPython stdout | Bella stdout |
|---|---|---|
| [streamdetail/readbytes](r32-probes/codex/streamdetail/readbytes) | `opening ⏎ reading ⏎ abc` | `opening ⏎ reading ⏎ radd ⏎ changed` |

## A32-21 · Low · Repeated reads of TextIOWrapper.newlines share one tuple

[Runnable row](r32-probes/codex/remaining/prog.py#L196) · [Captured outputs](r32-probes/codex/remaining/newlines)

At `runtime/prelude/_io.py:2533` the incremental decoder returns a tuple held in a module-level table. TextIOWrapper forwards this result at line 3325. When multiple newline forms have been seen, CPython builds a new tuple on each access.

```python
import io
f = io.TextIOWrapper(io.BytesIO(b"x\ry\r\nz\n"))
print(f.newlines)
f.read()
a, b = f.newlines, f.newlines
print(type(a).__name__, a, a is b)
```

| Row | CPython stdout | Bella stdout |
|---|---|---|
| [remaining/newlines](r32-probes/codex/remaining/newlines) | `None ⏎ tuple ('\r', '\n', '\r\n') False` | `None ⏎ tuple ('\r', '\n', '\r\n') True` |

## A32-22 · Low · A full-width struct string field returns the input bytes object

[Runnable row](r32-probes/codex/remaining/prog.py#L209) · [Captured outputs](r32-probes/codex/remaining/struct)

At `runtime/prelude/_struct.py:385`, unpack extracts an s field by slicing the bytes. A slice spanning the whole exact bytes object retains it. CPython materializes the field with PyBytes_FromStringAndSize (`Modules/_struct.c:2054`).

```python
import struct
class B(bytes): pass
x = B(b"hello")
a = struct.unpack("5s", x)[0]
print(type(a).__name__, a is x)
b = struct.unpack("5s", a)[0]
print(type(b).__name__, b is a)
```

| Row | CPython stdout | Bella stdout |
|---|---|---|
| [remaining/struct](r32-probes/codex/remaining/struct) | `bytes False ⏎ bytes False` | `bytes False ⏎ bytes True` |

## A32-23 · High · TextIOWrapper slices decoded text through a subclass override

[Runnable row](r32-probes/codex/streamdetail/prog.py#L63) · [Captured outputs](r32-probes/codex/streamdetail/readsizebytes)

At `runtime/prelude/_io.py:2604` a sized read extracts characters by subscripting the decoded string. Line 2729 does the same for a line fragment. CPython uses PyUnicode_Substring to copy code points. Bella can therefore return eight unrelated characters for read(2).

```python
import io, codecs
class S(str):
    def __getitem__(self,i):
        print("getitem")
        return "override"
class Dec(codecs.IncrementalDecoder):
    def decode(self,v,final=False): return S("abc") if v else ""
info=codecs.CodecInfo(None,None,incrementaldecoder=Dec,name="a32txt")
codecs.register(lambda s:info if s=="a32txt" else None)
class Buf(io.BytesIO):
    def writable(self): return False
print("opening")
f=io.TextIOWrapper(Buf(b"abc"),encoding="a32txt",newline="\n")
print("reading")
print(f.read(2))
```

| Row | CPython stdout | Bella stdout |
|---|---|---|
| [streamdetail/readsizebytes](r32-probes/codex/streamdetail/readsizebytes) | `opening ⏎ reading ⏎ ab` | `opening ⏎ reading ⏎ getitem ⏎ override` |
| [streamdetail/readlinebytes](r32-probes/codex/streamdetail/readlinebytes) | `opening ⏎ reading ⏎ abc` | `opening ⏎ reading ⏎ getitem ⏎ override` |

The readline row uses f.readline() in place of f.read(2). The opening and reading markers distinguish construction from the read.

## A32-24 · Medium · A one-direction buffered stream advertises its raw stream’s other direction

[Runnable row](r32-probes/codex/streamdetail/prog.py#L7) · [Captured outputs](r32-probes/codex/streamdetail/writable)

The method table at `runtime/prelude/_io.py:1925` installs both readable and writable on each buffered type. Lines 1869 and 1874 forward each call to the underlying object. CPython's BufferedReader.writable and BufferedWriter.readable return False for these inputs. This can prevent construction of a TextIOWrapper over a reader. At `runtime/prelude/_io.py:2915` Bella takes the encoder setup path for a codec with only an incremental decoder.

```python
import io
print(io.BufferedReader(io.BytesIO()).writable())
```

| Row | CPython stdout | Bella stdout |
|---|---|---|
| [streamdetail/writable](r32-probes/codex/streamdetail/writable) | `False` | `True` |
| [streamdetail/readable](r32-probes/codex/streamdetail/readable) | `False` | `True` |
| [streamdetail/readreader](r32-probes/codex/streamdetail/readreader) | `opening ⏎ reading ⏎ abc` | `opening ⏎ raised TypeError` |
| [streamdetail/readsizereader](r32-probes/codex/streamdetail/readsizereader) | `opening ⏎ reading ⏎ ab` | `opening ⏎ raised TypeError` |
| [streamdetail/readlinereader](r32-probes/codex/streamdetail/readlinereader) | `opening ⏎ reading ⏎ abc` | `opening ⏎ raised TypeError` |

The readable row uses `io.BufferedWriter(io.BytesIO()).readable()`. The other three rows wrap a BufferedReader in the decoder-only text stream from A32-23. CPython reaches the reading marker and reads text. Bella raises TypeError before that marker. Rows focused/{charsread,charsreadsize,charsreadline} show the same failed construction without the two progress markers.

## Checks that agreed

- All 84 stream-finalisation rows in [streams](r32-probes/codex/streams/prog.py) matched byte for byte. Those rows exercised the io base classes, concrete in-memory streams, FileIO, buffered streams, the pair and TextIOWrapper, with raising closed properties, overridden flush and close, subclass finalisers, and weak references. The file-backed warning tests also matched for reader, writer, random-access and text wrappers, raw files and pairs, including the warning source’s representation and the weak callback’s position.
- The [finaliser binding rows](r32-probes/codex/finalizers/prog.py) covered properties, partial and partialmethod, bound methods, a class as a finaliser, inherited classmethod, staticmethod around a builtin, list’s length descriptor, late assignment and deletion, instance-only assignment, resurrection, raising KeyboardInterrupt, and disposal of the return value. Outputs matched except for expected address text in two partial rows. The [ownership rows](r32-probes/codex/lifetime/prog.py) agreed on the order of finalisation for parent-held items, instance attributes and generators.
- The [struct sequence rows](r32-probes/codex/sequences/prog.py) agreed on constructor length boundaries, slicing, concatenation, visible-element equality and hash, repr, reduction, copy.copy, copy.replace and direct __replace__. These covered stat_result, terminal_size, times_result, uname_result, statvfs_result, sched_param, struct_time, struct_passwd and struct_group. Holding a slice, copy, replacement or reduce state across deletion also produced the same release sequence in the lifetime batch.
- The [display](r32-probes/codex/display/prog.py), [base-method](r32-probes/codex/basecalls/prog.py) and [return-type](r32-probes/codex/returntypes/prog.py) rows agreed on repr, str, format, percent conversions, f-strings, container repr and override calls for the tested numeric, text, bytes, container, exception and metaclass subclasses. The default object representations contained different addresses. The int/float conversion and KeyError rows agreed on whether the argument’s repr ran.
- All [mapping and collection mutation rows](r32-probes/codex/callbacks/prog.py) matched, including json.dumps with default callbacks that clear, append or replace list and dict entries, CSV row growth, mapping dispatch for execve and posix_spawn against a missing executable, partial keywords, format_map, Formatter, Counter, OrderedDict and ChainMap. Bisect and heapq agreed on the result or exception class and the final list contents when comparisons grew, cleared or replaced elements. The warning filter list could delete its active filter during match with the same subsequent callback order.
- The [identity batch](r32-probes/codex/identity/prog.py) agreed on the tested TypeAliasType fields, TypeVar names, getter and methodcaller reductions, Struct.format for subclass inputs, Unicode exception fields, Pattern.pattern, Match.string, and group, split and no-match substitution results for exact and subclass strings and bytes. In particular both sides returned the original exact str and a plain str for a subclass in the no-match substitution rows. The [path rows](r32-probes/codex/paths/prog.py) matched on fspath/fsencode/fsdecode, the tested absolute path operations, readlink, filenames for failed operations on path-like objects, and environment keys and values.
- GeneratorExit chains agreed for explicit close, deletion, nested handlers, finally, context manager exit, finaliser or weak callback, and three-deep delegation. The StopIteration-to-RuntimeError and ignored-GeneratorExit paths agreed on context, cause and suppression, including the outer handled exceptions. The [focused nested exception rows](r32-probes/codex/focused/prog.py) matched on conversions, dict and attribute lookup, import failure and encoding inside two nested handlers.
- The [remaining identity checks](r32-probes/codex/remaining/prog.py) agreed on repeated keys passed to JSON object_pairs_hook, warning category and filename identity and registry keys, stream buffer/raw/name access, and os.getcwd value and identity. The [custom-codec controls](r32-probes/codex/codecargs/prog.py) confirmed that generic encode/decode passed the original data object and returned the codec’s result object.
