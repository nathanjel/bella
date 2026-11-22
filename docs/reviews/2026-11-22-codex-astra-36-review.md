Codex `gpt-6.2-astra` at low reasoning effort, 2026-11-22, the cross-check the author asked for after each step. Verbatim. Tag A36 in the
review log. Its range is `d558f52..55c6f6d`, run non-interactively (standard input closed) in its own worktree (`bella-r36`) at `55c6f6d`: the
argument counts of the built-in types' methods and the fixes of review A35 (RL-777 to RL-802). Its probes (`r36-probes/codex/`) stayed in
that worktree. 37 findings; each was run on both sides by the session before any verdict (review log, A36).

---

# Bella conformance review A36

**37 verified differences on `55c6f6d` against CPython 3.15.2.** The 31 builds produced 1,416 paired process runs. Of those, 1,265 matched byte for byte, 140 reproduced the findings below, seven stopped by name, and four fell under the stated exclusions. Counts include the 37 reduced reproducers.

The failed setter for **exception.args** leaks every item yielded before an iterator error (A36-19). Object lifetime also changes returned data. **dict.update** copies a key list that CPython traverses live (A36-06), and the **JSON encoder** can omit an element appended by a finaliser (A36-33). After a failed **TextIOWrapper** reinitialisation, Bella can still read and write a stream CPython reports as closed (A36-22).

The review covers the three commits in `d558f52..55c6f6d`. A finding describes behaviour at the reviewed revision. Its inclusion does not date its introduction. High severity denotes a demonstrated leak, incorrect result or exception, or broadly observable store-order difference. Medium denotes a narrower protocol or finaliser-order difference.

## Reproduction

Run from the detached checkout. Set `suite=reduced` and `row=19` for A36-19, for example. Each linked evidence directory contains separate stdout, stderr and status files for each interpreter. All 37 reduced pairs exit 0 with empty stderr. Their caught exception classes and finalisers appear in stdout. Selecting a row starts just that example.

```bash
ulimit -v 8000000
export PYTHONHASHSEED=0
suite=reduced
row=19
prog=r36-probes/codex/$suite/prog.py
timeout 120 .venv/bin/python "$prog" "$row"
bin=$(timeout 600 ./r36-build "$prog")
timeout 120 "$bin" "$row"
```

Each finding also links a standalone Python file containing the same function body as its compiled row. I checked the standalone CPython output, stderr and status against the corresponding multiplexed CPython invocation.

## Findings by subject

| Subject | Findings |
|---|---|
| Iteration, unpacking and container operations | [A36-01](#a36-01), [A36-02](#a36-02), [A36-03](#a36-03), [A36-05](#a36-05), [A36-06](#a36-06), [A36-10](#a36-10), [A36-11](#a36-11), [A36-13](#a36-13), [A36-14](#a36-14), [A36-15](#a36-15), [A36-16](#a36-16), [A36-26](#a36-26), [A36-27](#a36-27), [A36-28](#a36-28), [A36-29](#a36-29), [A36-33](#a36-33), [A36-35](#a36-35), [A36-36](#a36-36) |
| Ownership and finaliser-visible state | [A36-09](#a36-09), [A36-17](#a36-17), [A36-19](#a36-19), [A36-21](#a36-21), [A36-23](#a36-23), [A36-24](#a36-24), [A36-25](#a36-25), [A36-30](#a36-30) |
| Construction and reinitialisation | [A36-04](#a36-04), [A36-08](#a36-08), [A36-20](#a36-20), [A36-22](#a36-22), [A36-31](#a36-31), [A36-32](#a36-32), [A36-34](#a36-34) |
| Typing and AST protocols | [A36-07](#a36-07), [A36-12](#a36-12), [A36-18](#a36-18), [A36-37](#a36-37) |

<a id="a36-01"></a>

## A36-01 · Medium · Failed unpacking releases the iterator and partial items in the wrong order

`runtime/src/ops.cpp:2167`

Bella accumulates owned references in a vector. The iterator leaves its nested scope first, then vector destruction releases elements in insertion order. CPython unwinds the partially filled stack in reverse before releasing the iterator. A traceback from __next__ can keep the iterator alive on both sides. The early-suite rows also verify that the finalisers still see the outer ArithmeticError.

[Minimal program](r36-probes/codex/reduced/01/example.py) · [Reduced row and raw outputs](r36-probes/codex/reduced/01)

| CPython stdout | Bella stdout |
|---|---|
| <code>next 1</code><br><code>next 2</code><br><code>next 3</code><br><code>drop 2</code><br><code>drop 1</code><br><code>iterator</code><br><code>end</code> | <code>next 1</code><br><code>next 2</code><br><code>next 3</code><br><code>iterator</code><br><code>drop 1</code><br><code>drop 2</code><br><code>end</code> |

<details><summary>Program and corroborating rows</summary>

```python
def example01():
    class T:
        def __init__(self, n): self.n = n
        def __del__(self): print("drop", self.n)
    class I:
        def __init__(self): self.n = 0
        def __iter__(self): return self
        def __next__(self):
            self.n += 1
            print("next", self.n)
            if self.n > 2: raise StopIteration
            return T(self.n)
        def __del__(self): print("iterator")
    class S:
        def __iter__(self): return I()
    try: a, b, c = S()
    except ValueError: pass
    print("end")

example01()
```

| Row | Program | CPython stdout | Bella stdout |
|---|---|---|---|
| [early/many](r36-probes/codex/early/many) | [source](r36-probes/codex/early/prog.py) | [c.out](r36-probes/codex/early/many/c.out) | [b.out](r36-probes/codex/early/many/b.out) |
| [early/few](r36-probes/codex/early/few) | [source](r36-probes/codex/early/prog.py) | [c.out](r36-probes/codex/early/few/c.out) | [b.out](r36-probes/codex/early/few/b.out) |
| [early/few-err](r36-probes/codex/early/few-err) | [source](r36-probes/codex/early/prog.py) | [c.out](r36-probes/codex/early/few-err/c.out) | [b.out](r36-probes/codex/early/few-err/b.out) |

</details>

<a id="a36-02"></a>

## A36-02 · Medium · A failed tuple conversion destroys accumulated elements from the front

`runtime/src/call.cpp:1473`

The catch block in c_tuple decrefs the partially accumulated vector from the front. CPython discards the partial tuple from the back. itertools.product uses the same tuple conversion to build its input pools (runtime/prelude/itertools.py:792).

[Minimal program](r36-probes/codex/reduced/02/example.py) · [Reduced row and raw outputs](r36-probes/codex/reduced/02)

| CPython stdout | Bella stdout |
|---|---|
| <code>drop 2</code><br><code>drop 1</code><br><code>end</code> | <code>drop 1</code><br><code>drop 2</code><br><code>end</code> |

<details><summary>Program and corroborating rows</summary>

```python
def example02():
    class T:
        def __init__(self, n): self.n = n
        def __del__(self): print("drop", self.n)
    def source():
        yield T(1)
        yield T(2)
        raise LookupError
    try: tuple(source())
    except LookupError: pass
    print("end")

example02()
```

| Row | Program | CPython stdout | Bella stdout |
|---|---|---|---|
| [early/tuple-err](r36-probes/codex/early/tuple-err) | [source](r36-probes/codex/early/prog.py) | [c.out](r36-probes/codex/early/tuple-err/c.out) | [b.out](r36-probes/codex/early/tuple-err/b.out) |
| [early/product-err](r36-probes/codex/early/product-err) | [source](r36-probes/codex/early/prog.py) | [c.out](r36-probes/codex/early/product-err/c.out) | [b.out](r36-probes/codex/early/product-err/b.out) |

</details>

<a id="a36-03"></a>

## A36-03 · Medium · map releases arguments of the completed callback in reverse order

`runtime/prelude/iterating.py:397`

The prelude appends each argument to a list, calls the function, and lets list destruction discard the items from the back. CPython map_next decrefs its argument stack in increasing index order. The map object itself releases its two iterators and the callable in the same order on both sides.

A third, empty input shows the same reversal on the early exit from map_next.

Strict map also reverses the partial argument releases, whether or not its previous result is held.

[Minimal program](r36-probes/codex/reduced/03/example.py) · [Reduced row and raw outputs](r36-probes/codex/reduced/03)

| CPython stdout | Bella stdout |
|---|---|
| <code>drop a</code><br><code>drop b</code><br><code>end</code> | <code>drop b</code><br><code>drop a</code><br><code>end</code> |

<details><summary>Program and corroborating rows</summary>

```python
def example03():
    class T:
        def __init__(self, n): self.n = n
        def __del__(self): print("drop", self.n)
    def one(n): yield T(n)
    next(map(lambda a, b: None, one("a"), one("b")))
    print("end")

example03()
```

| Row | Program | CPython stdout | Bella stdout |
|---|---|---|---|
| [fields/map](r36-probes/codex/fields/map) | [source](r36-probes/codex/fields/prog.py) | [c.out](r36-probes/codex/fields/map/c.out) | [b.out](r36-probes/codex/fields/map/b.out) |
| [edges/mapshort](r36-probes/codex/edges/mapshort) | [source](r36-probes/codex/edges/prog.py) | [c.out](r36-probes/codex/edges/mapshort/c.out) | [b.out](r36-probes/codex/edges/mapshort/b.out) |
| [ends/map-free](r36-probes/codex/ends/map-free) | [source](r36-probes/codex/ends/prog.py) | [c.out](r36-probes/codex/ends/map-free/c.out) | [b.out](r36-probes/codex/ends/map-free/b.out) |
| [ends/map-held](r36-probes/codex/ends/map-held) | [source](r36-probes/codex/ends/prog.py) | [c.out](r36-probes/codex/ends/map-held/c.out) | [b.out](r36-probes/codex/ends/map-held/b.out) |

</details>

<a id="a36-04"></a>

## A36-04 · High · TextIOWrapper refuses to delegate to a buffer retained after failed reinitialisation

`runtime/prelude/_io.py:3294`

The delegated methods and name getter check _a_ok before accessing _c_buffer. CPython buffer_access_safe returns a reference whenever the buffer pointer exists, even during incomplete initialisation. An invalid newline leaves the old buffer in place. Failure in a replacement buffer method exposes the new buffer. This changes both return values and exception classes.

Additional rows check buffer, name, fileno, isatty and the three capability methods. See the full method-by-method traces.

[Minimal program](r36-probes/codex/reduced/04/example.py) · [Reduced row and raw outputs](r36-probes/codex/reduced/04)

| CPython stdout | Bella stdout |
|---|---|
| <code>True</code><br><code>end</code> | <code>ValueError</code><br><code>end</code> |

<details><summary>Program and corroborating rows</summary>

```python
def example04():
    import io
    w = io.TextIOWrapper(io.BytesIO())
    try: w.__init__(io.BytesIO(), newline="bad")
    except ValueError: pass
    try: print(w.readable())
    except Exception as e: print(type(e).__name__)
    del w
    print("end")

example04()
```

| Row | Program | CPython stdout | Bella stdout |
|---|---|---|---|
| [reinit/Text-badnewline](r36-probes/codex/reinit/Text-badnewline) | [source](r36-probes/codex/reinit/prog.py) | [c.out](r36-probes/codex/reinit/Text-badnewline/c.out) | [b.out](r36-probes/codex/reinit/Text-badnewline/b.out) |
| [reinit/Text-badraw](r36-probes/codex/reinit/Text-badraw) | [source](r36-probes/codex/reinit/prog.py) | [c.out](r36-probes/codex/reinit/Text-badraw/c.out) | [b.out](r36-probes/codex/reinit/Text-badraw/b.out) |
| [reinit/Text-closedraw](r36-probes/codex/reinit/Text-closedraw) | [source](r36-probes/codex/reinit/prog.py) | [c.out](r36-probes/codex/reinit/Text-closedraw/c.out) | [b.out](r36-probes/codex/reinit/Text-closedraw/b.out) |
| [iomethods/TextIOWrapper-invalidbuf](r36-probes/codex/iomethods/TextIOWrapper-invalidbuf) | [source](r36-probes/codex/iomethods/prog.py) | [c.out](r36-probes/codex/iomethods/TextIOWrapper-invalidbuf/c.out) | [b.out](r36-probes/codex/iomethods/TextIOWrapper-invalidbuf/b.out) |
| [iomethods/TextIOWrapper-invalidnl](r36-probes/codex/iomethods/TextIOWrapper-invalidnl) | [source](r36-probes/codex/iomethods/prog.py) | [c.out](r36-probes/codex/iomethods/TextIOWrapper-invalidnl/c.out) | [b.out](r36-probes/codex/iomethods/TextIOWrapper-invalidnl/b.out) |
| [iomethods/TextIOWrapper-readable](r36-probes/codex/iomethods/TextIOWrapper-readable) | [source](r36-probes/codex/iomethods/prog.py) | [c.out](r36-probes/codex/iomethods/TextIOWrapper-readable/c.out) | [b.out](r36-probes/codex/iomethods/TextIOWrapper-readable/b.out) |
| [iomethods/TextIOWrapper-writable](r36-probes/codex/iomethods/TextIOWrapper-writable) | [source](r36-probes/codex/iomethods/prog.py) | [c.out](r36-probes/codex/iomethods/TextIOWrapper-writable/c.out) | [b.out](r36-probes/codex/iomethods/TextIOWrapper-writable/b.out) |
| [iomethods/TextIOWrapper-seekable](r36-probes/codex/iomethods/TextIOWrapper-seekable) | [source](r36-probes/codex/iomethods/prog.py) | [c.out](r36-probes/codex/iomethods/TextIOWrapper-seekable/c.out) | [b.out](r36-probes/codex/iomethods/TextIOWrapper-seekable/b.out) |
| [iomethods/TextIOWrapper-tell](r36-probes/codex/iomethods/TextIOWrapper-tell) | [source](r36-probes/codex/iomethods/prog.py) | [c.out](r36-probes/codex/iomethods/TextIOWrapper-tell/c.out) | [b.out](r36-probes/codex/iomethods/TextIOWrapper-tell/b.out) |

</details>

<a id="a36-05"></a>

## A36-05 · Medium · OrderedDict.fromkeys holds a discarded key across the next iterator call

`runtime/prelude/_collections.py:1272`

The loop leaves key bound after calling the subclass setter. CPython _PyDict_FromKeys releases its local key after each assignment. A setter that discards the key makes this visible even when all operations succeed.

[Minimal program](r36-probes/codex/reduced/05/example.py) · [Reduced row and raw outputs](r36-probes/codex/reduced/05)

| CPython stdout | Bella stdout |
|---|---|
| <code>next 1</code><br><code>drop 1</code><br><code>next 2</code><br><code>drop 2</code><br><code>next 3</code><br><code>iterator</code><br><code>end</code> | <code>next 1</code><br><code>next 2</code><br><code>drop 1</code><br><code>next 3</code><br><code>iterator</code><br><code>drop 2</code><br><code>end</code> |

<details><summary>Program and corroborating rows</summary>

```python
def example05():
    import collections
    class T:
        def __init__(self, n): self.n = n
        def __del__(self): print("drop", self.n)
    class I:
        def __init__(self): self.n = 0
        def __iter__(self): return self
        def __next__(self):
            self.n += 1
            print("next", self.n)
            if self.n > 2: raise StopIteration
            return T(self.n)
        def __del__(self): print("iterator")
    class S:
        def __iter__(self): return I()
    class D(collections.OrderedDict):
        def __setitem__(self, k, v): pass
    D.fromkeys(S())
    print("end")

example05()
```

| Row | Program | CPython stdout | Bella stdout |
|---|---|---|---|
| [protocol/od](r36-probes/codex/protocol/od) | [source](r36-probes/codex/protocol/prog.py) | [c.out](r36-probes/codex/protocol/od/c.out) | [b.out](r36-probes/codex/protocol/od/b.out) |

</details>

<a id="a36-06"></a>

## A36-06 · High · dict.update retains the keys iterator during mapping lookups

`runtime/src/ops.cpp:2230`

The runtime collects keys into a vector, but keeps the iterator in scope throughout the subsequent mapping lookups. CPython materialises the mapping keys before the merge loop and releases the temporary iterator when that materialisation finishes.

The same eager copy changes the result. CPython retains an exact list returned by keys() and iterates it live. Clearing that list during the first __getitem__ ends the merge. If keys() returns a custom iterator, CPython materialises it via PySequence_List, including a second iter call and a length hint. Bella bypasses both.

[Minimal program](r36-probes/codex/reduced/06/example.py) · [Reduced row and raw outputs](r36-probes/codex/reduced/06)

| CPython stdout | Bella stdout |
|---|---|
| <code>{'a': 1}</code><br><code>end</code> | <code>{'a': 1, 'b': 1}</code><br><code>end</code> |

<details><summary>Program and corroborating rows</summary>

```python
def example06():
    keys = ["a", "b"]
    class M:
        def keys(self): return keys
        def __getitem__(self, k): keys.clear(); return 1
    print(dict(M()))
    print("end")

example06()
```

| Row | Program | CPython stdout | Bella stdout |
|---|---|---|---|
| [protocol/keys](r36-probes/codex/protocol/keys) | [source](r36-probes/codex/protocol/prog.py) | [c.out](r36-probes/codex/protocol/keys/c.out) | [b.out](r36-probes/codex/protocol/keys/b.out) |
| [edges/livekeys](r36-probes/codex/edges/livekeys) | [source](r36-probes/codex/edges/prog.py) | [c.out](r36-probes/codex/edges/livekeys/c.out) | [b.out](r36-probes/codex/edges/livekeys/b.out) |
| [edges/hint](r36-probes/codex/edges/hint) | [source](r36-probes/codex/edges/prog.py) | [c.out](r36-probes/codex/edges/hint/c.out) | [b.out](r36-probes/codex/edges/hint/b.out) |

</details>

<a id="a36-07"></a>

## A36-07 · High · TypeVar substitution calls a user-defined index method

`runtime/prelude/_typing.py:398`

typevar_typing_prepare_subst_impl uses PySequence_Index, which obtains an iterator and compares elements. The prelude looks up the index attribute instead. This executes different user code and turns a successful substitution into RuntimeError.

[Minimal program](r36-probes/codex/reduced/07/example.py) · [Reduced row and raw outputs](r36-probes/codex/reduced/07)

| CPython stdout | Bella stdout |
|---|---|
| <code>(1,)</code><br><code>end</code> | <code>RuntimeError</code><br><code>end</code> |

<details><summary>Program and corroborating rows</summary>

```python
def example07():
    import typing
    t = typing.TypeVar("T")
    class P(tuple):
        def index(self, x): raise RuntimeError
    class A: __parameters__ = P((t,))
    try: print(t.__typing_prepare_subst__(A(), (1,)))
    except Exception as e: print(type(e).__name__)
    print("end")

example07()
```

| Row | Program | CPython stdout | Bella stdout |
|---|---|---|---|
| [protocol/typevar-index](r36-probes/codex/protocol/typevar-index) | [source](r36-probes/codex/protocol/prog.py) | [c.out](r36-probes/codex/protocol/typevar-index/c.out) | [b.out](r36-probes/codex/protocol/typevar-index/b.out) |

</details>

<a id="a36-08"></a>

## A36-08 · High · Changing __new__ loses the allocator-slot state used to check arguments

`runtime/src/types.cpp:592`

allocator_is_objects and type_call infer the allocator from the current MRO attributes. CPython update_one_slot can retain the existing tp_new when it rediscovers a built-in tp_new_wrapper after deletion. Conversely, explicitly assigning object.__new__ can preserve the object allocator. Reading the dictionary cannot distinguish those histories. This affects object.__init__ directly and the excess-argument checks during construction. The larger construct matrix also shows it on list, object, BufferedReader, BufferedWriter, BufferedRandom and TextIOWrapper.

[Minimal program](r36-probes/codex/reduced/08/example.py) · [Reduced row and raw outputs](r36-probes/codex/reduced/08)

| CPython stdout | Bella stdout |
|---|---|
| <code>None</code><br><code>end</code> | <code>TypeError</code><br><code>end</code> |

<details><summary>Program and corroborating rows</summary>

```python
def example08():
    class C: pass
    C.__new__ = staticmethod(lambda cls: object.__new__(cls))
    del C.__new__
    try: print(object.__init__(C(), 1))
    except Exception as e: print(type(e).__name__)
    print("end")

example08()
```

| Row | Program | CPython stdout | Bella stdout |
|---|---|---|---|
| [slots/object](r36-probes/codex/slots/object) | [source](r36-probes/codex/slots/prog.py) | [c.out](r36-probes/codex/slots/object/c.out) | [b.out](r36-probes/codex/slots/object/b.out) |
| [slots/objectalias](r36-probes/codex/slots/objectalias) | [source](r36-probes/codex/slots/prog.py) | [c.out](r36-probes/codex/slots/objectalias/c.out) | [b.out](r36-probes/codex/slots/objectalias/b.out) |
| [slots/list](r36-probes/codex/slots/list) | [source](r36-probes/codex/slots/prog.py) | [c.out](r36-probes/codex/slots/list/c.out) | [b.out](r36-probes/codex/slots/list/b.out) |
| [slots/reader](r36-probes/codex/slots/reader) | [source](r36-probes/codex/slots/prog.py) | [c.out](r36-probes/codex/slots/reader/c.out) | [b.out](r36-probes/codex/slots/reader/b.out) |
| [slots/writer](r36-probes/codex/slots/writer) | [source](r36-probes/codex/slots/prog.py) | [c.out](r36-probes/codex/slots/writer/c.out) | [b.out](r36-probes/codex/slots/writer/b.out) |
| [slots/random](r36-probes/codex/slots/random) | [source](r36-probes/codex/slots/prog.py) | [c.out](r36-probes/codex/slots/random/c.out) | [b.out](r36-probes/codex/slots/random/b.out) |
| [slots/text](r36-probes/codex/slots/text) | [source](r36-probes/codex/slots/prog.py) | [c.out](r36-probes/codex/slots/text/c.out) | [b.out](r36-probes/codex/slots/text/b.out) |
| [construct/BufferedReader](r36-probes/codex/construct/BufferedReader) | [source](r36-probes/codex/construct/prog.py) | [c.out](r36-probes/codex/construct/BufferedReader/c.out) | [b.out](r36-probes/codex/construct/BufferedReader/b.out) |
| [construct/BufferedWriter](r36-probes/codex/construct/BufferedWriter) | [source](r36-probes/codex/construct/prog.py) | [c.out](r36-probes/codex/construct/BufferedWriter/c.out) | [b.out](r36-probes/codex/construct/BufferedWriter/b.out) |
| [construct/BufferedRandom](r36-probes/codex/construct/BufferedRandom) | [source](r36-probes/codex/construct/prog.py) | [c.out](r36-probes/codex/construct/BufferedRandom/c.out) | [b.out](r36-probes/codex/construct/BufferedRandom/b.out) |
| [construct/TextIOWrapper](r36-probes/codex/construct/TextIOWrapper) | [source](r36-probes/codex/construct/prog.py) | [c.out](r36-probes/codex/construct/TextIOWrapper/c.out) | [b.out](r36-probes/codex/construct/TextIOWrapper/b.out) |
| [construct/list](r36-probes/codex/construct/list) | [source](r36-probes/codex/construct/prog.py) | [c.out](r36-probes/codex/construct/list/c.out) | [b.out](r36-probes/codex/construct/list/b.out) |
| [construct/object](r36-probes/codex/construct/object) | [source](r36-probes/codex/construct/prog.py) | [c.out](r36-probes/codex/construct/object/c.out) | [b.out](r36-probes/codex/construct/object/b.out) |

</details>

<a id="a36-09"></a>

## A36-09 · Medium · Dropping a Context destroys its last variable before its associated value

`runtime/prelude/_contextvars.py:357`

Bella stores the association in a dict. Clearing the sole entry releases the key and its default before the stored value. CPython hamt_node_bitmap_dealloc walks the node array backwards, releasing the value at index 1 before the key at index 0. This one-entry case is independent of hash and allocation order.

[Minimal program](r36-probes/codex/reduced/09/example.py) · [Reduced row and raw outputs](r36-probes/codex/reduced/09)

| CPython stdout | Bella stdout |
|---|---|
| <code>drop value</code><br><code>drop default</code><br><code>end</code> | <code>drop default</code><br><code>drop value</code><br><code>end</code> |

<details><summary>Program and corroborating rows</summary>

```python
def example09():
    import contextvars
    class T:
        def __init__(self, n): self.n = n
        def __del__(self): print("drop", self.n)
    c = contextvars.Context()
    c.run(contextvars.ContextVar("v", default=T("default")).set, T("value"))
    del c
    print("end")

example09()
```

| Row | Program | CPython stdout | Bella stdout |
|---|---|---|---|
| [owned/ctx](r36-probes/codex/owned/ctx) | [source](r36-probes/codex/owned/prog.py) | [c.out](r36-probes/codex/owned/ctx/c.out) | [b.out](r36-probes/codex/owned/ctx/b.out) |

</details>

<a id="a36-10"></a>

## A36-10 · Medium · pairwise and islice expose an internal StopIteration to finalisers

`runtime/prelude/itertools.py:237`

After obtaining the first item, the second next exhausts the input. The prelude drops old inside except BaseException. CPython pairwise_next clears its fields and decrefs old with the exception pending, leaving the caller’s handled KeyError visible.

The same handled-exception cleanup occurs at runtime/prelude/itertools.py:715. At its own stop limit islice raises StopIteration inside a try, catches it and clears the iterator in that handler. CPython islice_next goes directly to its empty label and clears the iterator there. With stop zero, no item or producer traceback is involved.

[Minimal program](r36-probes/codex/reduced/10/example.py) · [Reduced row and raw outputs](r36-probes/codex/reduced/10)

| CPython stdout | Bella stdout |
|---|---|
| <code>KeyError</code><br><code>end</code> | <code>StopIteration</code><br><code>end</code> |

<details><summary>Program and corroborating rows</summary>

```python
def example10():
    import itertools, sys
    class I:
        def __iter__(self): return self
        def __next__(self): return 1
        def __del__(self): print(type(sys.exception()).__name__)
    try: raise KeyError
    except KeyError: next(itertools.islice(I(), 0), None)
    print("end")

example10()
```

| Row | Program | CPython stdout | Bella stdout |
|---|---|---|---|
| [edges/pair](r36-probes/codex/edges/pair) | [source](r36-probes/codex/edges/prog.py) | [c.out](r36-probes/codex/edges/pair/c.out) | [b.out](r36-probes/codex/edges/pair/b.out) |
| [ends/slice-zero](r36-probes/codex/ends/slice-zero) | [source](r36-probes/codex/ends/prog.py) | [c.out](r36-probes/codex/ends/slice-zero/c.out) | [b.out](r36-probes/codex/ends/slice-zero/b.out) |
| [ends/slice-one](r36-probes/codex/ends/slice-one) | [source](r36-probes/codex/ends/prog.py) | [c.out](r36-probes/codex/ends/slice-one/c.out) | [b.out](r36-probes/codex/ends/slice-one/b.out) |

</details>

<a id="a36-11"></a>

## A36-11 · Medium · chain.from_iterable clears its source before releasing a non-iterable item

`runtime/prelude/itertools.py:757`

CPython chain_next_lock_held decrefs the rejected item immediately after PyObject_GetIter, then clears the source with the TypeError pending. The prelude clears the source in its handler while the item remains a local. The source finaliser sees the wrong exception as well as the wrong lifetime.

[Minimal program](r36-probes/codex/reduced/11/example.py) · [Reduced row and raw outputs](r36-probes/codex/reduced/11)

| CPython stdout | Bella stdout |
|---|---|
| <code>item</code><br><code>iterator NoneType</code><br><code>end</code> | <code>iterator TypeError</code><br><code>item</code><br><code>end</code> |

<details><summary>Program and corroborating rows</summary>

```python
def example11():
    import itertools, sys
    class I:
        def __iter__(self): return self
        def __next__(self): return X()
        def __del__(self): print("iterator", type(sys.exception()).__name__)
    class X:
        def __del__(self): print("item")
    class S:
        def __iter__(self): return I()
    try: next(itertools.chain.from_iterable(S()))
    except TypeError: pass
    print("end")

example11()
```

| Row | Program | CPython stdout | Bella stdout |
|---|---|---|---|
| [edges/chain](r36-probes/codex/edges/chain) | [source](r36-probes/codex/edges/prog.py) | [c.out](r36-probes/codex/edges/chain/c.out) | [b.out](r36-probes/codex/edges/chain/b.out) |

</details>

<a id="a36-12"></a>

## A36-12 · High · TypeVar substitution accepts a mapping as the sequence of supplied arguments

`runtime/prelude/_typing.py:399`

The C calls PySequence_Length. A dict has a mapping length but no sequence length. Python len(args) accepts it, and the prelude returns the mapping unchanged when the type variable index is within its size.

[Minimal program](r36-probes/codex/reduced/12/example.py) · [Reduced row and raw outputs](r36-probes/codex/reduced/12)

| CPython stdout | Bella stdout |
|---|---|
| <code>TypeError</code><br><code>end</code> | <code>{1: 2}</code><br><code>end</code> |

<details><summary>Program and corroborating rows</summary>

```python
def example12():
    import typing
    t = typing.TypeVar("T")
    class A: __parameters__ = (t,)
    try: print(t.__typing_prepare_subst__(A(), {1:2}))
    except Exception as e: print(type(e).__name__)
    print("end")

example12()
```

| Row | Program | CPython stdout | Bella stdout |
|---|---|---|---|
| [edges/params](r36-probes/codex/edges/params) | [source](r36-probes/codex/edges/prog.py) | [c.out](r36-probes/codex/edges/params/c.out) | [b.out](r36-probes/codex/edges/params/b.out) |

</details>

<a id="a36-13"></a>

## A36-13 · Medium · Starred unpacking skips the remainder iterator’s __iter__

`runtime/src/ops.cpp:2167`

After the leading targets, CPython uses PySequence_List(it) for the starred remainder. Bella asks the same iterator for its length hint and proceeds directly to for_next. This skips a user call even when the iterator returns itself. This row also shows the failed-unpack cleanup order in A36-01.

[Minimal program](r36-probes/codex/reduced/13/example.py) · [Reduced row and raw outputs](r36-probes/codex/reduced/13)

| CPython stdout | Bella stdout |
|---|---|
| <code>iter</code><br><code>end</code> | <code>end</code> |

<details><summary>Program and corroborating rows</summary>

```python
def example13():
    class I:
        def __iter__(self): print("iter"); return self
        def __next__(self): raise StopIteration
    class S:
        def __iter__(self): return I()
    a, *b = [0]
    try: a, *b = S()
    except ValueError: pass
    *b, = S()
    print("end")

example13()
```

| Row | Program | CPython stdout | Bella stdout |
|---|---|---|---|
| [edges/star](r36-probes/codex/edges/star) | [source](r36-probes/codex/edges/prog.py) | [c.out](r36-probes/codex/edges/star/c.out) | [b.out](r36-probes/codex/edges/star/b.out) |

</details>

<a id="a36-14"></a>

## A36-14 · Medium · sched_setaffinity retains a CPU item across the next iterator call

`runtime/prelude/posix.py:2166`

The prelude converts the CPU to an integer but keeps the original item bound. CPython decrefs the item immediately after PyLong_AsLong. The third iterator call raises before either implementation reaches the scheduler system call.

[Minimal program](r36-probes/codex/reduced/14/example.py) · [Reduced row and raw outputs](r36-probes/codex/reduced/14)

| CPython stdout | Bella stdout |
|---|---|
| <code>drop 1</code><br><code>next</code><br><code>end</code> | <code>next</code><br><code>drop 1</code><br><code>end</code> |

<details><summary>Program and corroborating rows</summary>

```python
def example14():
    import os
    class N(int):
        def __del__(self): print("drop", int(self))
    def source():
        yield N(1)
        print("next")
        raise LookupError
    try: os.sched_setaffinity(0, source())
    except LookupError: pass
    print("end")

example14()
```

| Row | Program | CPython stdout | Bella stdout |
|---|---|---|---|
| [consumers/affinity](r36-probes/codex/consumers/affinity) | [source](r36-probes/codex/consumers/prog.py) | [c.out](r36-probes/codex/consumers/affinity/c.out) | [b.out](r36-probes/codex/consumers/affinity/b.out) |

</details>

<a id="a36-15"></a>

## A36-15 · Medium · dict construction from pairs skips iterator protocol and unwinds a partial pair forwards

`runtime/src/call.cpp:1097`

dict_update_arg drains the pair iterator directly into a vector of Ref. CPython PySequence_Fast passes the iterator to PySequence_List, which requests its iterator and releases the partial list from the back on failure. Both the omitted call and the finaliser reversal are visible in this one pair.

[Minimal program](r36-probes/codex/reduced/15/example.py) · [Reduced row and raw outputs](r36-probes/codex/reduced/15)

| CPython stdout | Bella stdout |
|---|---|
| <code>iter</code><br><code>{1: 2}</code><br><code>end</code> | <code>{1: 2}</code><br><code>end</code> |

<details><summary>Program and corroborating rows</summary>

```python
def example15():
    class I:
        def __init__(self): self.i=0
        def __iter__(self): print("iter"); return self
        def __next__(self):
            self.i += 1
            if self.i > 2: raise StopIteration
            return self.i
    class Pair:
        def __iter__(self): return I()
    print(dict([Pair()]))
    print("end")

example15()
```

| Row | Program | CPython stdout | Bella stdout |
|---|---|---|---|
| [consumers/dictpair](r36-probes/codex/consumers/dictpair) | [source](r36-probes/codex/consumers/prog.py) | [c.out](r36-probes/codex/consumers/dictpair/c.out) | [b.out](r36-probes/codex/consumers/dictpair/b.out) |

</details>

<a id="a36-16"></a>

## A36-16 · Medium · OrderedDict pair cleanup runs in the wrong order on error

`runtime/prelude/_collections.py:1132`

The explicit del at the bottom of _od_add_pairs only runs on success. Failure while checking for a third value unwinds the locals in reverse. CPython mutablemapping_add_pairs uses the same Done label on success and failure, releasing pair, pair_iterator, key, then value.

[Minimal program](r36-probes/codex/reduced/16/example.py) · [Reduced row and raw outputs](r36-probes/codex/reduced/16)

| CPython stdout | Bella stdout |
|---|---|
| <code>pair</code><br><code>drop 1</code><br><code>drop 2</code><br><code>end</code> | <code>drop 2</code><br><code>drop 1</code><br><code>pair</code><br><code>end</code> |

<details><summary>Program and corroborating rows</summary>

```python
def example16():
    import collections
    class T:
        def __init__(self, n): self.n = n
        def __del__(self): print("drop", self.n)
    def source():
        yield T(1)
        yield T(2)
        raise LookupError
    class P:
        def __iter__(self): return source()
        def __del__(self): print("pair")
    def rows(): yield P()
    try: collections.OrderedDict(rows())
    except LookupError: pass
    print("end")

example16()
```

| Row | Program | CPython stdout | Bella stdout |
|---|---|---|---|
| [consumers/odpair](r36-probes/codex/consumers/odpair) | [source](r36-probes/codex/consumers/prog.py) | [c.out](r36-probes/codex/consumers/odpair/c.out) | [b.out](r36-probes/codex/consumers/odpair/b.out) |

</details>

<a id="a36-17"></a>

## A36-17 · Medium · TextIOWrapper destroys the decoder before the encoder

`runtime/prelude/_io.py:3024`

The slot order used at destruction and the explicit field resets during reinitialisation (line 3091) both put the decoder first. CPython textiowrapper_clear and the reset section of textiowrapper_init_impl both clear the encoder first. A registered codec with program-defined incremental encoder and decoder makes both drops observable.

[Minimal program](r36-probes/codex/reduced/17/example.py) · [Reduced row and raw outputs](r36-probes/codex/reduced/17)

| CPython stdout | Bella stdout |
|---|---|
| <code>encoder</code><br><code>decoder</code><br><code>end</code> | <code>decoder</code><br><code>encoder</code><br><code>end</code> |

<details><summary>Program and corroborating rows</summary>

```python
def example17():
    import codecs, io
    class Dec(codecs.IncrementalDecoder):
        def __del__(self): print("decoder")
    class Enc(codecs.IncrementalEncoder):
        def __del__(self): print("encoder")
    def search(name):
        return codecs.CodecInfo(name="a36", encode=None, decode=None,
                                incrementalencoder=Enc, incrementaldecoder=Dec)
    codecs.register(search)
    w = io.TextIOWrapper(io.BytesIO(), encoding="a36")
    del w
    codecs.unregister(search)
    print("end")

example17()
```

| Row | Program | CPython stdout | Bella stdout |
|---|---|---|---|
| [streams/fresh](r36-probes/codex/streams/fresh) | [source](r36-probes/codex/streams/prog.py) | [c.out](r36-probes/codex/streams/fresh/c.out) | [b.out](r36-probes/codex/streams/fresh/b.out) |
| [streams/again](r36-probes/codex/streams/again) | [source](r36-probes/codex/streams/prog.py) | [c.out](r36-probes/codex/streams/again/c.out) | [b.out](r36-probes/codex/streams/again/b.out) |
| [streams/fail](r36-probes/codex/streams/fail) | [source](r36-probes/codex/streams/prog.py) | [c.out](r36-probes/codex/streams/fail/c.out) | [b.out](r36-probes/codex/streams/fail/b.out) |
| [streams/close](r36-probes/codex/streams/close) | [source](r36-probes/codex/streams/prog.py) | [c.out](r36-probes/codex/streams/close/c.out) | [b.out](r36-probes/codex/streams/close/b.out) |
| [streams/detach](r36-probes/codex/streams/detach) | [source](r36-probes/codex/streams/prog.py) | [c.out](r36-probes/codex/streams/detach/c.out) | [b.out](r36-probes/codex/streams/detach/b.out) |

</details>

<a id="a36-18"></a>

## A36-18 · High · AST methods accept an exact dict as the field sequence

`runtime/prelude/_ast.py:165`

AST initialisation, repr (line 112), reduction (223), and replacement (242) use len(fields). CPython uses PySequence_Size on the field container. An exact dict has a mapping length and lacks the sequence length slot. Even an empty dict is enough for all four operations to diverge. The control dict subclass with a Python __len__ agreed.

[Minimal program](r36-probes/codex/reduced/18/example.py) · [Reduced row and raw outputs](r36-probes/codex/reduced/18)

| CPython stdout | Bella stdout |
|---|---|
| <code>TypeError</code><br><code>end</code> | <code>ok</code><br><code>end</code> |

<details><summary>Program and corroborating rows</summary>

```python
def example18():
    import ast
    class A(ast.AST): _fields = {}
    try: A(); print("ok")
    except Exception as e: print(type(e).__name__)
    print("end")

example18()
```

| Row | Program | CPython stdout | Bella stdout |
|---|---|---|---|
| [concrete/ast-init-dict](r36-probes/codex/concrete/ast-init-dict) | [source](r36-probes/codex/concrete/prog.py) | [c.out](r36-probes/codex/concrete/ast-init-dict/c.out) | [b.out](r36-probes/codex/concrete/ast-init-dict/b.out) |
| [concrete/ast-repr-dict](r36-probes/codex/concrete/ast-repr-dict) | [source](r36-probes/codex/concrete/prog.py) | [c.out](r36-probes/codex/concrete/ast-repr-dict/c.out) | [b.out](r36-probes/codex/concrete/ast-repr-dict/b.out) |
| [concrete/ast-reduce-dict](r36-probes/codex/concrete/ast-reduce-dict) | [source](r36-probes/codex/concrete/prog.py) | [c.out](r36-probes/codex/concrete/ast-reduce-dict/c.out) | [b.out](r36-probes/codex/concrete/ast-reduce-dict/b.out) |
| [concrete/ast-replace-dict](r36-probes/codex/concrete/ast-replace-dict) | [source](r36-probes/codex/concrete/prog.py) | [c.out](r36-probes/codex/concrete/ast-replace-dict/c.out) | [b.out](r36-probes/codex/concrete/ast-replace-dict/b.out) |

</details>

<a id="a36-19"></a>

## A36-19 · High · Failed assignment to exception.args leaks every item produced before the error

`runtime/src/types.cpp:2858`

exception_args_set releases each owned Ref into a vector of raw Obj handles. If for_next throws, the vector storage is freed but its elements receive no decref. CPython PySequence_Tuple decrefs the partial tuple in reverse before propagating the error. The original args remain intact on both sides.

[Minimal program](r36-probes/codex/reduced/19/example.py) · [Reduced row and raw outputs](r36-probes/codex/reduced/19)

| CPython stdout | Bella stdout |
|---|---|
| <code>drop 2</code><br><code>drop 1</code><br><code>end</code> | <code>end</code> |

<details><summary>Program and corroborating rows</summary>

```python
def example19():
    class T:
        def __init__(self, n): self.n = n
        def __del__(self): print("drop", self.n)
    def source():
        yield T(1)
        yield T(2)
        raise LookupError
    e = ValueError()
    try: e.args = source()
    except LookupError: pass
    del e
    print("end")

example19()
```

| Row | Program | CPython stdout | Bella stdout |
|---|---|---|---|
| [typeitems/args-fail](r36-probes/codex/typeitems/args-fail) | [source](r36-probes/codex/typeitems/prog.py) | [c.out](r36-probes/codex/typeitems/args-fail/c.out) | [b.out](r36-probes/codex/typeitems/args-fail/b.out) |

</details>

<a id="a36-20"></a>

## A36-20 · High · Custom metaclass mro results are validated before their iterator is exhausted

`runtime/src/types.cpp:697`

CPython materialises the entire result of mro() as a tuple before mro_check. Bella validates each element during iteration, so a non-class first element suppresses later __next__ calls and can replace the iterator’s LookupError with TypeError.

[Minimal program](r36-probes/codex/reduced/20/example.py) · [Reduced row and raw outputs](r36-probes/codex/reduced/20)

| CPython stdout | Bella stdout |
|---|---|
| <code>LookupError</code><br><code>end</code> | <code>TypeError</code><br><code>end</code> |

<details><summary>Program and corroborating rows</summary>

```python
def example20():
    class M(type):
        def mro(cls):
            yield 1
            raise LookupError
    try:
        class C(metaclass=M): pass
    except Exception as e: print(type(e).__name__)
    print("end")

example20()
```

| Row | Program | CPython stdout | Bella stdout |
|---|---|---|---|
| [typeitems/mro-fail](r36-probes/codex/typeitems/mro-fail) | [source](r36-probes/codex/typeitems/prog.py) | [c.out](r36-probes/codex/typeitems/mro-fail/c.out) | [b.out](r36-probes/codex/typeitems/mro-fail/b.out) |
| [typeitems/mro-ok](r36-probes/codex/typeitems/mro-ok) | [source](r36-probes/codex/typeitems/prog.py) | [c.out](r36-probes/codex/typeitems/mro-ok/c.out) | [b.out](r36-probes/codex/typeitems/mro-ok/b.out) |

</details>

<a id="a36-21"></a>

## A36-21 · Medium · Invalid __slots__ iterables release the temporary names in forward order

`runtime/src/types.cpp:796`

The type constructor collects Ref elements into a vector that releases from the front, both when iteration fails and when the later validation rejects the names. The temporary CPython tuple releases from the back.

[Minimal program](r36-probes/codex/reduced/21/example.py) · [Reduced row and raw outputs](r36-probes/codex/reduced/21)

| CPython stdout | Bella stdout |
|---|---|
| <code>drop 2</code><br><code>drop 1</code><br><code>end</code> | <code>drop 1</code><br><code>drop 2</code><br><code>end</code> |

<details><summary>Program and corroborating rows</summary>

```python
def example21():
    class T:
        def __init__(self, n): self.n = n
        def __del__(self): print("drop", self.n)
    def source():
        yield T(1)
        yield T(2)
        raise LookupError
    try:
        class C: __slots__ = source()
    except LookupError: pass
    print("end")

example21()
```

| Row | Program | CPython stdout | Bella stdout |
|---|---|---|---|
| [typeitems/slots-fail](r36-probes/codex/typeitems/slots-fail) | [source](r36-probes/codex/typeitems/prog.py) | [c.out](r36-probes/codex/typeitems/slots-fail/c.out) | [b.out](r36-probes/codex/typeitems/slots-fail/b.out) |
| [typeitems/slots-ok](r36-probes/codex/typeitems/slots-ok) | [source](r36-probes/codex/typeitems/prog.py) | [c.out](r36-probes/codex/typeitems/slots-ok/c.out) | [b.out](r36-probes/codex/typeitems/slots-ok/b.out) |

</details>

<a id="a36-22"></a>

## A36-22 · High · Invalid errors argument leaves a reinitialised TextIOWrapper usable

`runtime/prelude/_io.py:3072`

CPython argument clinic converts encoding, newline and the two boolean flags, then the implementation sets ok to zero before validating errors. Bella validates errors before resetting _a_ok. After TypeError, the original wrapper still reads, writes, flushes and detaches in Bella. CPython reports closed and raises ValueError on these operations.

[Minimal program](r36-probes/codex/reduced/22/example.py) · [Reduced row and raw outputs](r36-probes/codex/reduced/22)

| CPython stdout | Bella stdout |
|---|---|
| <code>True</code><br><code>end</code> | <code>False</code><br><code>end</code> |

<details><summary>Program and corroborating rows</summary>

```python
def example22():
    import io
    w = io.TextIOWrapper(io.BytesIO())
    try: w.__init__(io.BytesIO(), errors=0)
    except TypeError: print(w.closed)
    del w
    print("end")

example22()
```

| Row | Program | CPython stdout | Bella stdout |
|---|---|---|---|
| [iomethods/TextIOWrapper-errors](r36-probes/codex/iomethods/TextIOWrapper-errors) | [source](r36-probes/codex/iomethods/prog.py) | [c.out](r36-probes/codex/iomethods/TextIOWrapper-errors/c.out) | [b.out](r36-probes/codex/iomethods/TextIOWrapper-errors/b.out) |

</details>

<a id="a36-23"></a>

## A36-23 · High · Reassigning two fast locals finalises their old values in the opposite order

`pipeline/l2/lower.py:302`

Bella emits target stores in source order. For the literal RHS in this example CPython emits STORE_FAST_STORE_FAST (b, a) after evaluating the two new values. The difference first appeared before exception reinitialisation in exceptionstate/{AttributeError,ImportError,ModuleNotFoundError,NameError}-omit. The isolated probe needs no exception.

[Minimal program](r36-probes/codex/reduced/23/example.py) · [Reduced row and raw outputs](r36-probes/codex/reduced/23)

| CPython stdout | Bella stdout |
|---|---|
| <code>drop b</code><br><code>drop a</code><br><code>end</code> | <code>drop a</code><br><code>drop b</code><br><code>end</code> |

<details><summary>Program and corroborating rows</summary>

```python
def example23():
    class T:
        def __init__(self, n): self.n = n
        def __del__(self): print("drop", self.n)
    a, b = T("a"), T("b")
    a, b = (), {}
    print("end")

example23()
```

| Row | Program | CPython stdout | Bella stdout |
|---|---|---|---|
| [reentrant/assign](r36-probes/codex/reentrant/assign) | [source](r36-probes/codex/reentrant/prog.py) | [c.out](r36-probes/codex/reentrant/assign/c.out) | [b.out](r36-probes/codex/reentrant/assign/b.out) |
| [exceptionstate/AttributeError-omit](r36-probes/codex/exceptionstate/AttributeError-omit) | [source](r36-probes/codex/exceptionstate/prog.py) | [c.out](r36-probes/codex/exceptionstate/AttributeError-omit/c.out) | [b.out](r36-probes/codex/exceptionstate/AttributeError-omit/b.out) |
| [exceptionstate/ImportError-omit](r36-probes/codex/exceptionstate/ImportError-omit) | [source](r36-probes/codex/exceptionstate/prog.py) | [c.out](r36-probes/codex/exceptionstate/ImportError-omit/c.out) | [b.out](r36-probes/codex/exceptionstate/ImportError-omit/b.out) |
| [exceptionstate/ModuleNotFoundError-omit](r36-probes/codex/exceptionstate/ModuleNotFoundError-omit) | [source](r36-probes/codex/exceptionstate/prog.py) | [c.out](r36-probes/codex/exceptionstate/ModuleNotFoundError-omit/c.out) | [b.out](r36-probes/codex/exceptionstate/ModuleNotFoundError-omit/b.out) |
| [exceptionstate/NameError-omit](r36-probes/codex/exceptionstate/NameError-omit) | [source](r36-probes/codex/exceptionstate/prog.py) | [c.out](r36-probes/codex/exceptionstate/NameError-omit/c.out) | [b.out](r36-probes/codex/exceptionstate/NameError-omit/b.out) |

</details>

<a id="a36-24"></a>

## A36-24 · High · The old StopIteration value sees its replacement during finalisation

`runtime/src/types.cpp:2782`

After BaseException_init has replaced args, CPython explicitly clears value and only installs the new value once the old one has been decrefed. Bella uses a single field replacement. A finaliser can read the exception through its existing owner and branch on value is None. Also observed in exceptionstate/StopIteration-again.

[Minimal program](r36-probes/codex/reduced/24/example.py) · [Reduced row and raw outputs](r36-probes/codex/reduced/24)

| CPython stdout | Bella stdout |
|---|---|
| <code>True</code><br><code>end</code> | <code>False</code><br><code>end</code> |

<details><summary>Program and corroborating rows</summary>

```python
def example24():
    owner = []
    class T:
        def __del__(self): print(owner[0].value is None)
    e = StopIteration(T())
    owner.append(e)
    e.__init__(1)
    owner.clear()
    del e
    print("end")

example24()
```

| Row | Program | CPython stdout | Bella stdout |
|---|---|---|---|
| [reentrant/stop](r36-probes/codex/reentrant/stop) | [source](r36-probes/codex/reentrant/prog.py) | [c.out](r36-probes/codex/reentrant/stop/c.out) | [b.out](r36-probes/codex/reentrant/stop/b.out) |
| [exceptionstate/StopIteration-again](r36-probes/codex/exceptionstate/StopIteration-again) | [source](r36-probes/codex/exceptionstate/prog.py) | [c.out](r36-probes/codex/exceptionstate/StopIteration-again/c.out) | [b.out](r36-probes/codex/exceptionstate/StopIteration-again/b.out) |

</details>

<a id="a36-25"></a>

## A36-25 · Medium · SyntaxError releases text before its ending line and column

`runtime/src/core.cpp:861`

The native field list puts text before end_lineno and end_offset. SyntaxError_clear releases these two fields before text. Removing the shared reference from args makes the field order visible. Also observed after repeated initialisation in exceptionstate/SyntaxError-omit and SyntaxError-partial.

[Minimal program](r36-probes/codex/reduced/25/example.py) · [Reduced row and raw outputs](r36-probes/codex/reduced/25)

| CPython stdout | Bella stdout |
|---|---|
| <code>drop end line</code><br><code>drop end offset</code><br><code>drop text</code><br><code>end</code> | <code>drop text</code><br><code>drop end line</code><br><code>drop end offset</code><br><code>end</code> |

<details><summary>Program and corroborating rows</summary>

```python
def example25():
    class T:
        def __init__(self, n): self.n = n
        def __del__(self): print("drop", self.n)
    e = SyntaxError("msg", (0, 0, 0, T("text"), T("end line"), T("end offset")))
    e.args = ()
    del e
    print("end")

example25()
```

| Row | Program | CPython stdout | Bella stdout |
|---|---|---|---|
| [reentrant/syntax](r36-probes/codex/reentrant/syntax) | [source](r36-probes/codex/reentrant/prog.py) | [c.out](r36-probes/codex/reentrant/syntax/c.out) | [b.out](r36-probes/codex/reentrant/syntax/b.out) |
| [exceptionstate/SyntaxError-omit](r36-probes/codex/exceptionstate/SyntaxError-omit) | [source](r36-probes/codex/exceptionstate/prog.py) | [c.out](r36-probes/codex/exceptionstate/SyntaxError-omit/c.out) | [b.out](r36-probes/codex/exceptionstate/SyntaxError-omit/b.out) |
| [exceptionstate/SyntaxError-partial](r36-probes/codex/exceptionstate/SyntaxError-partial) | [source](r36-probes/codex/exceptionstate/prog.py) | [c.out](r36-probes/codex/exceptionstate/SyntaxError-partial/c.out) | [b.out](r36-probes/codex/exceptionstate/SyntaxError-partial/b.out) |

</details>

<a id="a36-26"></a>

## A36-26 · Medium · reduce releases its iterator before the last reference to the accumulator on callback failure

`runtime/prelude/_functools.py:490`

The old value remains in result while the prelude calls func. On failure the explicit cleanup is skipped and unwinding drops the iterator before the result local. CPython transfers ownership of the prior result into the two-argument tuple. Its cleanup releases the tuple (second operand then accumulator), then the iterator. operator.add fails inside the built-in with no Python callback frame retaining operands.

[Minimal program](r36-probes/codex/reduced/26/example.py) · [Reduced row and raw outputs](r36-probes/codex/reduced/26)

| CPython stdout | Bella stdout |
|---|---|
| <code>next 1</code><br><code>next 2</code><br><code>drop 2</code><br><code>drop 1</code><br><code>iterator</code><br><code>end</code> | <code>next 1</code><br><code>next 2</code><br><code>drop 2</code><br><code>iterator</code><br><code>drop 1</code><br><code>end</code> |

<details><summary>Program and corroborating rows</summary>

```python
def example26():
    import functools, operator
    class T:
        def __init__(self, n): self.n = n
        def __del__(self): print("drop", self.n)
    class I:
        def __init__(self): self.n = 0
        def __iter__(self): return self
        def __next__(self):
            self.n += 1
            print("next", self.n)
            if self.n > 2: raise StopIteration
            return T(self.n)
        def __del__(self): print("iterator")
    class S:
        def __iter__(self): return I()
    try: functools.reduce(operator.add, S())
    except TypeError: pass
    print("end")

example26()
```

| Row | Program | CPython stdout | Bella stdout |
|---|---|---|---|
| [failure/reduce](r36-probes/codex/failure/reduce) | [source](r36-probes/codex/failure/prog.py) | [c.out](r36-probes/codex/failure/reduce/c.out) | [b.out](r36-probes/codex/failure/reduce/b.out) |

</details>

<a id="a36-27"></a>

## A36-27 · Medium · writelines releases the iterator before an invalid line

`runtime/prelude/_io.py:2419`

A buffer conversion error bypasses del item. Unwinding the for loop destroys the iterator wrapper before the item local. CPython _io_BytesIO_writelines_impl decrefs item immediately after write_bytes_lock_held, then decrefs the iterator on the error branch.

The shared _IOBase.writelines loop at runtime/prelude/_io.py:552 also skips its release when write raises. The same order inversion occurs on a StringIO, a TextIOWrapper and a BufferedWriter.

[Minimal program](r36-probes/codex/reduced/27/example.py) · [Reduced row and raw outputs](r36-probes/codex/reduced/27)

| CPython stdout | Bella stdout |
|---|---|
| <code>next 1</code><br><code>drop 1</code><br><code>iterator</code><br><code>end</code> | <code>next 1</code><br><code>iterator</code><br><code>drop 1</code><br><code>end</code> |

<details><summary>Program and corroborating rows</summary>

```python
def example27():
    import io
    class T:
        def __init__(self, n): self.n = n
        def __del__(self): print("drop", self.n)
    class I:
        def __init__(self): self.n = 0
        def __iter__(self): return self
        def __next__(self):
            self.n += 1
            print("next", self.n)
            if self.n > 2: raise StopIteration
            return T(self.n)
        def __del__(self): print("iterator")
    class S:
        def __iter__(self): return I()
    try: io.BytesIO().writelines(S())
    except TypeError: pass
    print("end")

example27()
```

| Row | Program | CPython stdout | Bella stdout |
|---|---|---|---|
| [failure/writelines](r36-probes/codex/failure/writelines) | [source](r36-probes/codex/failure/prog.py) | [c.out](r36-probes/codex/failure/writelines/c.out) | [b.out](r36-probes/codex/failure/writelines/b.out) |
| [loops/write-string](r36-probes/codex/loops/write-string) | [source](r36-probes/codex/loops/prog.py) | [c.out](r36-probes/codex/loops/write-string/c.out) | [b.out](r36-probes/codex/loops/write-string/b.out) |
| [loops/write-text](r36-probes/codex/loops/write-text) | [source](r36-probes/codex/loops/prog.py) | [c.out](r36-probes/codex/loops/write-text/c.out) | [b.out](r36-probes/codex/loops/write-text/b.out) |
| [loops/write-buffer](r36-probes/codex/loops/write-buffer) | [source](r36-probes/codex/loops/prog.py) | [c.out](r36-probes/codex/loops/write-buffer/c.out) | [b.out](r36-probes/codex/loops/write-buffer/b.out) |

</details>

<a id="a36-28"></a>

## A36-28 · Medium · The CSV reader keeps a physical line while requesting the next line of a quoted field

`runtime/prelude/_csv.py:298`

The normal sweep covers records that fit on one physical line. Reader.__next__ loops for a multiline record without unbinding line. CPython Reader_iternext decrefs the physical line before reading the next. Both readers parse the same quoted field, but the producer observes a different lifetime.

[Minimal program](r36-probes/codex/reduced/28/example.py) · [Reduced row and raw outputs](r36-probes/codex/reduced/28)

| CPython stdout | Bella stdout |
|---|---|
| <code>drop</code><br><code>next</code><br><code>['xy']</code><br><code>end</code> | <code>next</code><br><code>drop</code><br><code>['xy']</code><br><code>end</code> |

<details><summary>Program and corroborating rows</summary>

```python
def example28():
    import csv
    class S(str):
        def __del__(self): print("drop")
    def lines():
        yield S('"x')
        print("next")
        yield 'y"'
    print(next(csv.reader(lines())))
    print("end")

example28()
```

| Row | Program | CPython stdout | Bella stdout |
|---|---|---|---|
| [loops/csv](r36-probes/codex/loops/csv) | [source](r36-probes/codex/loops/prog.py) | [c.out](r36-probes/codex/loops/csv/c.out) | [b.out](r36-probes/codex/loops/csv/b.out) |

</details>

<a id="a36-29"></a>

## A36-29 · Medium · Signal-set conversion holds each signal object across the next call

`runtime/prelude/_signal.py:226`

Both the signal prelude and posix.py:834 implement _Py_Sigset_Converter with a Python loop that retains item after numeric conversion. The C converter decrefs the object before advancing the iterator. This reaches all four tested signal calls and the two posix_spawn signal keywords. In all six probes the iterator raises before the requested system operation.

[Minimal program](r36-probes/codex/reduced/29/example.py) · [Reduced row and raw outputs](r36-probes/codex/reduced/29)

| CPython stdout | Bella stdout |
|---|---|
| <code>drop 1</code><br><code>next</code><br><code>end</code> | <code>next</code><br><code>drop 1</code><br><code>end</code> |

<details><summary>Program and corroborating rows</summary>

```python
def example29():
    import signal
    class N(int):
        def __del__(self): print("drop", int(self))
    def source():
        yield N(1)
        print("next")
        raise LookupError
    try: signal.pthread_sigmask(signal.SIG_BLOCK, source())
    except LookupError: pass
    print("end")

example29()
```

| Row | Program | CPython stdout | Bella stdout |
|---|---|---|---|
| [loops/sigmask](r36-probes/codex/loops/sigmask) | [source](r36-probes/codex/loops/prog.py) | [c.out](r36-probes/codex/loops/sigmask/c.out) | [b.out](r36-probes/codex/loops/sigmask/b.out) |
| [loops/sigwait](r36-probes/codex/loops/sigwait) | [source](r36-probes/codex/loops/prog.py) | [c.out](r36-probes/codex/loops/sigwait/c.out) | [b.out](r36-probes/codex/loops/sigwait/b.out) |
| [loops/sigwaitinfo](r36-probes/codex/loops/sigwaitinfo) | [source](r36-probes/codex/loops/prog.py) | [c.out](r36-probes/codex/loops/sigwaitinfo/c.out) | [b.out](r36-probes/codex/loops/sigwaitinfo/b.out) |
| [loops/sigtimedwait](r36-probes/codex/loops/sigtimedwait) | [source](r36-probes/codex/loops/prog.py) | [c.out](r36-probes/codex/loops/sigtimedwait/c.out) | [b.out](r36-probes/codex/loops/sigtimedwait/b.out) |
| [loops/spawn-mask](r36-probes/codex/loops/spawn-mask) | [source](r36-probes/codex/loops/prog.py) | [c.out](r36-probes/codex/loops/spawn-mask/c.out) | [b.out](r36-probes/codex/loops/spawn-mask/b.out) |
| [loops/spawn-default](r36-probes/codex/loops/spawn-default) | [source](r36-probes/codex/loops/prog.py) | [c.out](r36-probes/codex/loops/spawn-default/c.out) | [b.out](r36-probes/codex/loops/spawn-default/b.out) |

</details>

<a id="a36-30"></a>

## A36-30 · High · TextIOWrapper drops an exact FileIO that CPython retains after detach

`runtime/prelude/_io.py:3120`

CPython caches an additional owned raw pointer when an exact BufferedReader, BufferedWriter or BufferedRandom wraps an exact FileIO. The prelude only holds the buffer. Detaching the text stream or independently detaching the buffered stream and dropping its other owners exposes the missing reference. The FileIO name object is the finaliser witness.

The cached raw stream also affects reads. Reinitialise the buffered reader with an open BytesIO, then close the old FileIO. CPython checks the cached FileIO for closure, while Bella reads from the replacement buffer. The second CPython ValueError is from closing the wrapper in the probe’s finally block. Leaving the old FileIO open agrees.

[Minimal program](r36-probes/codex/reduced/30/example.py) · [Reduced row and raw outputs](r36-probes/codex/reduced/30)

| CPython stdout | Bella stdout |
|---|---|
| <code>release</code><br><code>drop path</code><br><code>end</code> | <code>drop path</code><br><code>release</code><br><code>end</code> |

<details><summary>Program and corroborating rows</summary>

```python
def example30():
    import io, os
    class Path:
        def __fspath__(self): return os.devnull
        def __del__(self): print("drop path")
    w = io.TextIOWrapper(io.BufferedReader(io.FileIO(Path())))
    w.detach()
    print("release")
    del w
    print("end")

example30()
```

| Row | Program | CPython stdout | Bella stdout |
|---|---|---|---|
| [loops/raw-text](r36-probes/codex/loops/raw-text) | [source](r36-probes/codex/loops/prog.py) | [c.out](r36-probes/codex/loops/raw-text/c.out) | [b.out](r36-probes/codex/loops/raw-text/b.out) |
| [loops/raw-buffer](r36-probes/codex/loops/raw-buffer) | [source](r36-probes/codex/loops/prog.py) | [c.out](r36-probes/codex/loops/raw-buffer/c.out) | [b.out](r36-probes/codex/loops/raw-buffer/b.out) |
| [protocol2/raw-closed](r36-probes/codex/protocol2/raw-closed) | [source](r36-probes/codex/protocol2/prog.py) | [c.out](r36-probes/codex/protocol2/raw-closed/c.out) | [b.out](r36-probes/codex/protocol2/raw-closed/b.out) |

</details>

<a id="a36-31"></a>

## A36-31 · High · A CSV iterator base suppresses an allocator inherited from another base

`runtime/src/types.cpp:541`

base_has_no_tp_new follows tp_base, checking only classes along that chain for a Python __new__. A mixin supplying the allocator can occur elsewhere in the MRO. CPython invokes it for the subclass in either base order. The integer return demonstrates that the allocator ran without creating a reader or writer. Directly assigning the allocator on the subclass agreed.

[Minimal program](r36-probes/codex/reduced/31/example.py) · [Reduced row and raw outputs](r36-probes/codex/reduced/31)

| CPython stdout | Bella stdout |
|---|---|
| <code>17</code><br><code>end</code> | <code>TypeError</code><br><code>end</code> |

<details><summary>Program and corroborating rows</summary>

```python
def example31():
    import csv
    class M:
        def __new__(cls): return 17
    class C(type(csv.reader([])), M): pass
    try: print(C())
    except Exception as e: print(type(e).__name__)
    print("end")

example31()
```

| Row | Program | CPython stdout | Bella stdout |
|---|---|---|---|
| [machinery/csvr-first](r36-probes/codex/machinery/csvr-first) | [source](r36-probes/codex/machinery/prog.py) | [c.out](r36-probes/codex/machinery/csvr-first/c.out) | [b.out](r36-probes/codex/machinery/csvr-first/b.out) |
| [machinery/csvr-second](r36-probes/codex/machinery/csvr-second) | [source](r36-probes/codex/machinery/prog.py) | [c.out](r36-probes/codex/machinery/csvr-second/c.out) | [b.out](r36-probes/codex/machinery/csvr-second/b.out) |
| [machinery/csvw-first](r36-probes/codex/machinery/csvw-first) | [source](r36-probes/codex/machinery/prog.py) | [c.out](r36-probes/codex/machinery/csvw-first/c.out) | [b.out](r36-probes/codex/machinery/csvw-first/b.out) |
| [machinery/csvw-second](r36-probes/codex/machinery/csvw-second) | [source](r36-probes/codex/machinery/prog.py) | [c.out](r36-probes/codex/machinery/csvw-second/c.out) | [b.out](r36-probes/codex/machinery/csvw-second/b.out) |

</details>

<a id="a36-32"></a>

## A36-32 · High · Repeated OSError initialisation preserves stale errno and strerror

`runtime/src/types.cpp:2248`

On a subclass that overrides __init__ and inherits OSError.__new__, the native initialiser parses the arguments again. Outside the special two-through-five argument range, CPython replaces errno and strerror with null pointers. Bella guards both assignments on a parsed value being present. The args tuple changes while the old errno and strerror survive. The two filename fields legitimately survive on both sides.

[Minimal program](r36-probes/codex/reduced/32/example.py) · [Reduced row and raw outputs](r36-probes/codex/reduced/32)

| CPython stdout | Bella stdout |
|---|---|
| <code>None None</code><br><code>end</code> | <code>5 old</code><br><code>end</code> |

<details><summary>Program and corroborating rows</summary>

```python
def example32():
    class E(OSError):
        def __init__(self, *a): super().__init__(*a)
    e = E(5, "old")
    e.__init__()
    print(e.errno, e.strerror)
    print("end")

example32()
```

| Row | Program | CPython stdout | Bella stdout |
|---|---|---|---|
| [machinery/os-zero](r36-probes/codex/machinery/os-zero) | [source](r36-probes/codex/machinery/prog.py) | [c.out](r36-probes/codex/machinery/os-zero/c.out) | [b.out](r36-probes/codex/machinery/os-zero/b.out) |
| [machinery/os-one](r36-probes/codex/machinery/os-one) | [source](r36-probes/codex/machinery/prog.py) | [c.out](r36-probes/codex/machinery/os-one/c.out) | [b.out](r36-probes/codex/machinery/os-one/b.out) |
| [machinery/os-six](r36-probes/codex/machinery/os-six) | [source](r36-probes/codex/machinery/prog.py) | [c.out](r36-probes/codex/machinery/os-six/c.out) | [b.out](r36-probes/codex/machinery/os-six/b.out) |

</details>

<a id="a36-33"></a>

## A36-33 · High · A finaliser can change the JSON text because the encoder holds the current element too long

`runtime/prelude/_json.py:755`

The sequence loop leaves obj bound while testing the next index against the live length. The mapping-items loop similarly retains item across its size check (line 710). CPython releases the iteration reference before checking the length again. The default callback clears the container, and the finaliser appends two entries. CPython serialises the second appended entry. Bella ends the loop before the finaliser can extend it. The exact-dict control agrees.

[Minimal program](r36-probes/codex/reduced/33/example.py) · [Reduced row and raw outputs](r36-probes/codex/reduced/33)

| CPython stdout | Bella stdout |
|---|---|
| <code>[1, 9]</code><br><code>end</code> | <code>[1]</code><br><code>end</code> |

<details><summary>Program and corroborating rows</summary>

```python
def example33():
    import json
    state = []
    class T:
        def __del__(self): state.extend([8, 9])
    def default(obj): state.clear(); return 1
    state.append(T())
    print(json.dumps(state, default=default))
    print("end")

example33()
```

| Row | Program | CPython stdout | Bella stdout |
|---|---|---|---|
| [jsonloop/list](r36-probes/codex/jsonloop/list) | [source](r36-probes/codex/jsonloop/prog.py) | [c.out](r36-probes/codex/jsonloop/list/c.out) | [b.out](r36-probes/codex/jsonloop/list/b.out) |
| [jsonloop/pairs](r36-probes/codex/jsonloop/pairs) | [source](r36-probes/codex/jsonloop/prog.py) | [c.out](r36-probes/codex/jsonloop/pairs/c.out) | [b.out](r36-probes/codex/jsonloop/pairs/b.out) |

</details>

<a id="a36-34"></a>

## A36-34 · High · The abstract-class allocator drops names that CPython keeps across iterator advances and bypasses their comparisons

`runtime/src/types.cpp:570`

This is a next_after loop where early release is observable and incorrect. CPython builds a list of the original abstract-method name objects and sorts it with PyList_Sort. Bella saves their UTF-8 text in a vector, drops each name before the next call and sorts native strings. A str subclass can raise ArithmeticError from its comparison, replacing the abstract-class TypeError in CPython only.

[Minimal program](r36-probes/codex/reduced/34/example.py) · [Reduced row and raw outputs](r36-probes/codex/reduced/34)

| CPython stdout | Bella stdout |
|---|---|
| <code>ArithmeticError</code><br><code>end</code> | <code>TypeError</code><br><code>end</code> |

<details><summary>Program and corroborating rows</summary>

```python
def example34():
    class Name(str):
        def __lt__(self, other): raise ArithmeticError
    class C: pass
    C.__abstractmethods__ = [Name("b"), Name("a")]
    try: C()
    except Exception as e: print(type(e).__name__)
    del C.__abstractmethods__
    print("end")

example34()
```

| Row | Program | CPython stdout | Bella stdout |
|---|---|---|---|
| [abstract/ok](r36-probes/codex/abstract/ok) | [source](r36-probes/codex/abstract/prog.py) | [c.out](r36-probes/codex/abstract/ok/c.out) | [b.out](r36-probes/codex/abstract/ok/b.out) |
| [abstract/sort-error](r36-probes/codex/abstract/sort-error) | [source](r36-probes/codex/abstract/prog.py) | [c.out](r36-probes/codex/abstract/sort-error/c.out) | [b.out](r36-probes/codex/abstract/sort-error/b.out) |
| [abstract/iter-error](r36-probes/codex/abstract/iter-error) | [source](r36-probes/codex/abstract/prog.py) | [c.out](r36-probes/codex/abstract/iter-error/c.out) | [b.out](r36-probes/codex/abstract/iter-error/b.out) |

</details>

<a id="a36-35"></a>

## A36-35 · Medium · Deque comparison retains both items across iterator advances and releases the iterators in reverse

`runtime/prelude/_collections.py:347`

The comparison loop binds x and y across the next pair of next calls. CPython deque_richcompare decrefs x then y before advancing, and releases it1 then it2 on exit. Bella unwinds local variables on return, releasing the right operand and iterator first. The life row agrees on the equality result. The lt row isolates the release order on an early return with an agreeing result.

[Minimal program](r36-probes/codex/reduced/35/example.py) · [Reduced row and raw outputs](r36-probes/codex/reduced/35)

| CPython stdout | Bella stdout |
|---|---|
| <code>drop a</code><br><code>drop b</code><br><code>next a</code><br><code>next b</code><br><code>True</code><br><code>end</code> | <code>next a</code><br><code>drop a</code><br><code>next b</code><br><code>drop b</code><br><code>True</code><br><code>end</code> |

<details><summary>Program and corroborating rows</summary>

```python
def example35():
    import collections
    class T:
        def __init__(self, n): self.n = n
        def __del__(self): print("drop", self.n)
    class D(collections.deque):
        def __iter__(self):
            yield T(self.tag)
            print("next", self.tag)
    T.__eq__ = lambda self, other: True
    a, b = D(), D()
    a.tag, b.tag = "a", "b"
    print(a == b)
    print("end")

example35()
```

| Row | Program | CPython stdout | Bella stdout |
|---|---|---|---|
| [compare/life](r36-probes/codex/compare/life) | [source](r36-probes/codex/compare/prog.py) | [c.out](r36-probes/codex/compare/life/c.out) | [b.out](r36-probes/codex/compare/life/b.out) |
| [compare/lt](r36-probes/codex/compare/lt) | [source](r36-probes/codex/compare/prog.py) | [c.out](r36-probes/codex/compare/lt/c.out) | [b.out](r36-probes/codex/compare/lt/b.out) |

</details>

<a id="a36-36"></a>

## A36-36 · High · Deque equality and inequality skip an element comparison and can return the opposite boolean

`runtime/prelude/_collections.py:356`

After the first unequal pair, CPython calls PyObject_RichCompareBool again using the requested operation, including EQ or NE. Bella returns False for EQ and True for NE without that call. A stateful __eq__ and an independent __ne__ show both wrong results.

[Minimal program](r36-probes/codex/reduced/36/example.py) · [Reduced row and raw outputs](r36-probes/codex/reduced/36)

| CPython stdout | Bella stdout |
|---|---|
| <code>ne</code><br><code>False</code><br><code>end</code> | <code>True</code><br><code>end</code> |

<details><summary>Program and corroborating rows</summary>

```python
def example36():
    import collections
    class T:
        def __eq__(self, other): return False
        def __ne__(self, other): print("ne"); return False
    print(collections.deque([T()]) != collections.deque([T()]))
    print("end")

example36()
```

| Row | Program | CPython stdout | Bella stdout |
|---|---|---|---|
| [compare/eq](r36-probes/codex/compare/eq) | [source](r36-probes/codex/compare/prog.py) | [c.out](r36-probes/codex/compare/eq/c.out) | [b.out](r36-probes/codex/compare/eq/b.out) |
| [compare/ne](r36-probes/codex/compare/ne) | [source](r36-probes/codex/compare/prog.py) | [c.out](r36-probes/codex/compare/ne/c.out) | [b.out](r36-probes/codex/compare/ne/b.out) |

</details>

<a id="a36-37"></a>

## A36-37 · High · TypeVar applies numeric addition when CPython requires sequence concatenation

`runtime/prelude/_typing.py:405`

When supplying a default, typevar_typing_prepare_subst_impl calls PySequence_Concat. A class that only supplies __len__ and __add__ has a usable length and a numeric add slot but cannot participate in that sequence fallback. The prelude uses ordinary +, calls __add__, and returns its arbitrary result. The control also implementing __getitem__ agrees.

[Minimal program](r36-probes/codex/reduced/37/example.py) · [Reduced row and raw outputs](r36-probes/codex/reduced/37)

| CPython stdout | Bella stdout |
|---|---|
| <code>TypeError</code><br><code>end</code> | <code>7</code><br><code>end</code> |

<details><summary>Program and corroborating rows</summary>

```python
def example37():
    import typing
    t = typing.TypeVar("T", default=int)
    class A: __parameters__ = (t,)
    class Args:
        def __len__(self): return 0
        def __add__(self, x): return 7
    try: print(t.__typing_prepare_subst__(A(), Args()))
    except Exception as e: print(type(e).__name__)
    print("end")

example37()
```

| Row | Program | CPython stdout | Bella stdout |
|---|---|---|---|
| [protocol2/subst-len](r36-probes/codex/protocol2/subst-len) | [source](r36-probes/codex/protocol2/prog.py) | [c.out](r36-probes/codex/protocol2/subst-len/c.out) | [b.out](r36-probes/codex/protocol2/subst-len/b.out) |

</details>

## Coverage and agreeing checks

The two constructor sweeps used 168 factory rows and 391 rows covering the factories plus additional exposed classes. They exercised class-body overrides, assignment and deletion of hooks, mixed bases, metaclass dispatch, `object.__new__`, `Sub.__new__`, explicit base initialisation, copying and reduction. Of the 391 class-body rows, 388 matched and three stopped by name. In the runtime’s CPython flag table the only types marked both subclassable and disallow-instantiation are the CSV reader and writer types. Creating either subclass succeeds on both sides. Instantiating a plain subclass raises TypeError on both sides. A mixin supplying the allocator exposes A36-31. [Dynamic constructor matrix](r36-probes/codex/construct/prog.py) · [Class-body and copy matrix](r36-probes/codex/shapes/prog.py)

The row programs record the exact arguments and callbacks exercised. Some combinations of field contents, subclasses and failing initialisation steps remain untested. Private implementation helpers and unsupported paths did not all yield constructible test objects. The seven named stops, individual object addresses, exit-time effects of traceback cycles, and the existing struct iterator buffer issue are excluded from the findings.

* All 77 exception rows with independent argument, instance-dict and frame-local witnesses agreed on release order after raising through a closure. The matching controls include normal exception-group matching, tuple-based except clauses and generator delegation completed through next, send and throw. [Exception evidence](r36-probes/codex/exceptions) · [Delegation evidence](r36-probes/codex/protocol2)
* Of 178 tagged object and subclass transition rows, 177 matched byte for byte. One printed a default object address. Covered objects include deque iterators, slotted and dictionary-bearing subclasses, functools wrappers, itertools objects mid-iteration, CSV readers and writers, the JSON scanner and encoder, IO types, descriptors and typing objects. [Transition evidence](r36-probes/codex/transitions)
* 163 of the 164 additional holder rows matched. These included field-bearing AST nodes, regex scanners, format iterators, templates, weak proxies and locks. All three bounded/unbounded cache release and eviction rows in the early-exit suite agreed. [Holder evidence](r36-probes/codex/holders) · [Cache evidence](r36-probes/codex/ends)
* BufferedReader, BufferedWriter and BufferedRandom agreed on the tested failed raw-stream callbacks, size conversions and post-failure methods. All 17 replacement rows for FileIO, StringIO, method wrappers, mappings and super agreed. [IO method evidence](r36-probes/codex/iomethods) · [Replacement evidence](r36-probes/codex/replacements)
* Protocol controls included GenericAlias comparison, hashing, iterating, calling, substitution and reduction with subclass properties, union comparison, weak-reference equality and callbacks, struct format caching and CSV dialect validation. The 13 GenericAlias subclass rows matched. [Alias evidence](r36-probes/codex/aliases) · [Concrete API evidence](r36-probes/codex/concrete)
* Among the early-error and short-circuit controls, list and deque construction on iterator failure, set intersection and disjointness, membership, any/all, strict zip with a retained previous result, and min/max with a failing key agreed on output, handled exception and exit status. [Early exits](r36-probes/codex/early) · [Failure paths](r36-probes/codex/failure) · [Shorter inputs](r36-probes/codex/ends)
