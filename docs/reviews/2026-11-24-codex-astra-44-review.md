Codex `gpt-6.2-astra` at low reasoning effort, 2026-11-24. Verbatim. Tag A44 in the review log. Range `2c342bc..756222f`:
classes as counted objects (`756222f`, C-3-12, D-19, RL-929, RL-932), a step that changes what programs do broadly (the
author's rule of 2026-11-22), together with A43's fixes and `_abc`'s weak references (`de36608`), batched into one review
as that rule says. Run non-interactively (standard input closed) in its own worktree (`bella-r44`), the prompt worded as
conformance. Probes (`r44-probes/codex/`) stayed in that worktree; the session ran every row of the 27 probe programs
again before any verdict (review log, A44).

---

# A44 — Bella conformance at 756222f

Range `2c342bc..756222f`. Each row runs in a fresh process from the checkout root with `ulimit -v 8000000` and `PYTHONHASHSEED=0`. Let P be a probe directory such as `r44-probes/codex/collect`. Build with `timeout 600 ./r44-build P/prog.py`. Run `timeout 120 .venv/bin/python P/prog.py ROW` and `timeout 120 BINARY ROW`, where BINARY is the path printed by the build. Exact programs and separate stdout, stderr and status files are under `P/ROW` (program one directory above the outputs).

## A44-01 · Medium · DEBUG_SAVEALL omits the dead class's namespace and MRO

`runtime/include/bella/object.hpp:2648`, `runtime/src/types.cpp:1795`. Rows [savedict](r44-probes/codex/collect/savedict) and [savemro](r44-probes/codex/collect/savemro) in [collect/prog.py](r44-probes/codex/collect/prog.py). CPython prints `True\n` in each. Bella prints `False\n` in each. Both sides have empty stderr and exit 0. The predicates test membership by contents. Neither depends on collection counts or ordering.

Reduced program (select one predicate per run):

```python
import gc
gc.disable()
class Base: pass
gc.set_debug(gc.DEBUG_SAVEALL)
def make():
    class Child(Base):
        mark = 'A44'
make()
gc.collect()
print(any(isinstance(x, dict) and x.get('mark') == 'A44' for x in gc.garbage))
# Second row uses this predicate instead:
# print(any(isinstance(x, tuple) and len(x) == 3 and x[1] is Base for x in gc.garbage))
gc.set_debug(0)
gc.garbage.clear()
```

CPython's type traversal visits the namespace dict and the MRO tuple, both concrete objects that the collector can hand to the program through `gc.garbage`. Bella walks the attribute values and MRO classes directly. It visits the corresponding container objects only if a view or tuple has already been materialised. Neither probe reads the namespace or MRO before collection.

## A44-02 · High · Changing a metaclass hash makes an existing ABC cache entry miss

`runtime/src/abc.cpp:137`. Run [abchash/prog.py](r44-probes/codex/abchash/prog.py) with row [change](r44-probes/codex/abchash/change). Both exit 0 with empty stderr. CPython stdout is `again\nFalse\n`. Bella stdout is `again\nhash\nhash\nFalse\n`. The application never creates or hashes a weak reference.

```python
import abc, gc
gc.disable()
class A(abc.ABC): pass
class M(type): pass
class C(metaclass=M): pass
class Old: pass
def changed(cls):
    print('hash')
    return 12
issubclass(Old, A)
issubclass(C, A)
M.__hash__ = changed
print('again')
print(issubclass(C, A))
```

The first lookup for C in a nonempty negative cache computes the basic reference's hash. CPython reuses it on the second lookup. Bella's plain-metaclass fast path uses the current object hash without recording it. After the metaclass changes, Bella invokes the replacement during lookup, misses, and invokes it again when inserting a new cache reference. This is observable using ABC operations alone.

The [abcanswer/change](r44-probes/codex/abcanswer/change) row makes the wrong cache miss change the public answer. Its [minimal program](r44-probes/codex/abcanswer/prog.py) gives A a subclass hook that returns a global boolean. After caching False it changes both the metaclass hash and the boolean. CPython prints `False\nFalse\n`, Bella prints `False\nTrue\n`. Both exit 0 with empty stderr.

## A44-03 · Medium · Clearing the input slot list finalises its name while the class is still live

`runtime/src/types.cpp:981`, `runtime/include/bella/object.hpp:1166`. Run [slotname/prog.py](r44-probes/codex/slotname/prog.py) with row [clear](r44-probes/codex/slotname/clear). CPython stdout is `kept\ngone\ndone\n`. Bella stdout is `gone\nkept\ndone\n`. Both exit 0 with empty stderr.

```python
import gc
gc.disable()
class S(str):
    def __del__(self): print('gone')
def make():
    names = [S('field')]
    C = type('C', (), {'__slots__': names})
    names.clear()
    return C
C = make()
gc.collect()
print('kept')
del C
gc.collect()
print('done')
```

CPython stores the sorted slot names in the heap type's own `ht_slots` tuple. For this unmangled name it keeps the original string subclass instance. Bella sorts the objects but converts the result to text and interns it. Clearing the input list therefore releases the last reference to the program's name object prematurely.

## A44-04 · High · A base exposes a subclass before its metaclass has supplied an MRO

`runtime/include/bella/object.hpp:1155` and `:1163`, `runtime/src/types.cpp:1061`. Run [construction/prog.py](r44-probes/codex/construction/prog.py) with [normal](r44-probes/codex/construction/normal) or [fail](r44-probes/codex/construction/fail). All four runs exit 0 with empty stderr.

| Row | CPython stdout | Bella stdout |
|---|---|---|
| normal | `False\n1 False\n0 True\n` | `True\n1 False\n0 True\n` |
| fail | `False\n0 True\n0 True\n` | `True\n1 False\n0 True\n` |

```python
import gc, sys, weakref
gc.disable()
refs = []
class Base: pass
class M(type):
    def mro(cls):
        print(cls in Base.__subclasses__())
        refs.append(weakref.ref(cls))
        if sys.argv[1] == 'fail': raise ValueError
        return super().mro()
def make():
    try:
        class Child(Base, metaclass=M): pass
    except ValueError: pass
make()
print(len(Base.__subclasses__()), refs[0]() is None)
gc.collect()
print(len(Base.__subclasses__()), refs[0]() is None)
```

Bella installs a default MRO, counts its reference to the new class, and enters the subclass in each base before invoking the metaclass. CPython adds the subclass in `type_ready_add_subclasses`, after MRO calculation succeeds. On failure, the CPython row loses the unfinished class immediately. Bella keeps its self-reference and exposes the failed definition to later callers until collection.

The same premature MRO is visible directly in [mrotuple/building](r44-probes/codex/mrotuple/building). Inside `M.mro(cls)`, `print(cls.__mro__ is None)` prints `True\n` on CPython and `False\n` on Bella. Both exit 0 with empty stderr. [Program](r44-probes/codex/mrotuple/prog.py)

Two further rows show consequences of installing C3 first:

- [customc3/resolve](r44-probes/codex/customc3/resolve) defines `A(X,Y)` and `B(Y,X)`. The metaclass of `C(A,B)` prints `mro` and returns `(cls,A,B,X,Y,object)`. CPython calls it and accepts the class. Bella fails the preliminary C3 merge before the hook runs. CPython prints `mro\nTrue\n`, Bella prints `TypeError\n` from the program's handler. [Minimal program](r44-probes/codex/customc3/prog.py)
- [mroread/stale](r44-probes/codex/mroread/stale) reads `cls.__mro__` inside the hook, then returns `(cls,Side,object)`. The new class inherits `Side.x` on both sides. CPython prints `1 True\n` for `print(C.x, Side in C.__mro__)`, Bella prints `1 False\n`. Bella cached its preliminary tuple on the read, and `ClassObject::set_mro` at `runtime/include/bella/object.hpp:961` leaves that tuple in place. [Minimal program](r44-probes/codex/mroread/prog.py)

All four runs exit 0 with empty stderr.

## A44-05 · Medium · A metaclass's exact MRO tuple loses its identity

`runtime/src/types.cpp:832` and `:1795`. Run [mrotuple/prog.py](r44-probes/codex/mrotuple/prog.py) with [identity](r44-probes/codex/mrotuple/identity). CPython stdout is `True\n`, Bella stdout is `False\n`. Both exit 0 with empty stderr.

```python
hold = []
class M(type):
    def mro(cls):
        result = tuple(super().mro())
        hold.append(result)
        return result
class C(metaclass=M): pass
print(C.__mro__ is hold[0])
```

CPython keeps the exact tuple returned by the metaclass. Bella extracts its entries, passes a vector of classes to `set_mro`, then lets the tuple go. Reading `__mro__` materialises another tuple.

## A44-06 · Medium · A string subclass assigned as a class name runs an extra finaliser at exit

`runtime/src/call.cpp:3708`, `runtime/src/types.cpp:1615`. Run [exitname/prog.py](r44-probes/codex/exitname/prog.py) with [normal](r44-probes/codex/exitname/normal), [qual](r44-probes/codex/exitname/qual), or [cycle](r44-probes/codex/exitname/cycle). CPython stdout is empty in all three. Bella prints `name\n` in each. Both sides exit 0 with empty stderr.

```python
import gc, os
gc.disable()
class N(str):
    def __del__(self, w=os.write): w(1, b'name\n')
class C: pass
C.__name__ = N('label')
```

The qual row assigns `__qualname__`. The cycle row additionally gives the name a reference to C. CPython's `type_traverse` deliberately skips `ht_name` and `ht_qualname`. The reference to the name counts as external during trial deletion, and the Python finaliser's globals lead back to C. Bella keeps assigned names in static strong-reference tables. Its exit collector also marks objects reached from lost modules as unreachable before finalising, without first reconciling those external counts. A name may then go with a class or remain in the table until process teardown. The [external](r44-probes/codex/external/prog.py) variant distinguishes the two timings. CPython prints nothing. Bella prints `name False\n` for normal and `name True\n` for cycle, reporting whether sys.stdout is None. All stderr streams are empty and statuses zero.

Two controls isolate the difference. Storing the same object as an ordinary class attribute prints `name\n` on both sides. Dropping C and explicitly collecting before shutdown prints `name\ncollected\n` on both sides.

## Coverage limits

The 200,000-class `singledispatch` row completed under CPython. Bella reached the 120-second limit with empty stdout and stderr. The same program completed and matched at 2,048 classes. The larger row establishes a timeout, not a hang. General `__class__` reassignment and some function-local dataclass constructions reached named stops. A module-level dataclass completed on both sides.

## Checks that agreed

- **Class lifetime.** Retaining a slot descriptor, method with a class cell, bound `super()`, instance in a global or list, MRO tuple, dictionary keyed by class, or derived class kept the expected objects alive. Clearing those holders and collecting produced identical callback and finaliser multisets. A decorator's captured state, a method default, a closure, and an exception subclass retained through a caught exception and its traceback followed the same lifetime on both sides.
- **Collection and resurrection.** A finaliser read a class attribute while its class was being collected. Resurrecting either the instance or its class gave the same results, including the surviving subclass entry, a fresh weak reference taken after resurrection, and removal of the subclass after the second collection. Class/instance cycles over twelve built-in bases, including numeric types, variable-sized containers and Exception, each ran the finaliser once and released the class.
- **Factories and ABCs.** Dynamic `type`, a dataclass, Enum, NamedTuple, namedtuple and TypedDict classes died at the same checkpoints. An LRU cache retained the class until cleared. References from all three ABC sets cleared when their targets died. Retained dump entries and callbacks showed empty backing sets after collection or registry/cache reset. Their backing sets died with the ABC. A metaclass hash raising a TypeError subclass propagated the same exception object.
- **Churn.** Two 200,000-class rows completed with identical stdout `200000 0\n`, empty stderr and status 0. They checked calls, cached properties, class keys, assigned names, ordinary type checks and `__init_subclass__` counts while collecting every 128 iterations. The ABC row additionally alternated registered and unregistered classes. The smaller dispatch control printed `2048 0\n` on both sides.
- **Exit.** A stream retained by a class and installed in stdout or stderr saw the same two flushes and finalisation. Separate probes placed state on a local metaclass, its class, or a class/instance cycle and observed identical shutdown state through `os.write`. A program importing and exercising the requested standard-library closure after constructing 1,024 classes agreed byte for byte on normal exit and `sys.exit(19)`. On the uncaught ValueError row stdout, status 1, exception class and message agreed. Stderr differed by the source line and underline covered by D-06.
