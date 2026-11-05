Codex astra-low, 2026-11-05, as the author passed it on. Verbatim. Tag A11 in the review log. Its
range is `62d083b..0081164`, and it tested `0081164` in a separate checkout.

---

Found **4 defects**, all **P2**. Tested isolated commit `0081164` using the configured **CPython 3.15.2** and `pipeline/build.py --run`. Your working-tree changes were untouched.

**1. User classes inherit built-in finality by name** — [runtime/src/types.cpp:534](/tmp/bella-review-0081164/runtime/src/types.cpp:534)

```python
class range:
    pass
class C(range):
    pass
print(isinstance(C(), range))
```

CPython:
```text
True
```

Bella exits 1:
```text
TypeError: type 'range' is not an acceptable base type
```

The `final` table lookup uses `bc->name` without establishing that the base is the corresponding built-in type. Ordinary user classes named `range`, `bool`, etc. become incorrectly unsubclassable.

**2. Class dict views captured during `mro()` stay stale** — [runtime/src/types.cpp:638](/tmp/bella-review-0081164/runtime/src/types.cpp:638)

```python
class M(type):
    def mro(cls):
        global view
        view = cls.__dict__.keys()
        return [cls, object]
class C(metaclass=M): pass
print('__doc__' in C.__dict__, '__doc__' in view)
```

CPython:
```text
True True
```

Bella:
```text
True False
```

After invoking `mro()`, class creation inserts `__doc__` directly through `attrs.set`, bypassing `set_attr` and its live-view synchronization. The neighboring insertions of `__dict__` and implicit `__hash__ = None` reproduce the same defect.

**3. Explicit sequence `__add__` incorrectly invokes reflected operators** — [runtime/src/slots.cpp:98](/tmp/bella-review-0081164/runtime/src/slots.cpp:98)

```python
class R:
    def __radd__(self, other): return 'reflected'
try:
    print([].__add__(R()))
except TypeError:
    print('TypeError')
```

CPython:
```text
TypeError
```

Bella:
```text
reflected
```

`own_add` calls general `binary` dispatch, which tries the other operand’s `__radd__`. An explicit `list.__add__` call must perform list concatenation directly. Also reproduced with strings and tuples.

**4. `_abc_init` iterates mapping-items results twice** — [runtime/src/abc.cpp:96](/tmp/bella-review-0081164/runtime/src/abc.cpp:96)

```python
import _abc
class M:
    def items(self): return self
    def __iter__(self):
        print('iter')
        return iter(())
class C:
    __dict__ = M()
    __bases__ = ()
_abc._abc_init(C())
```

CPython:
```text
iter
```

Bella:
```text
iter
iter
```

`mapping_items` creates and discards an iterator for validation, then `list_extend` requests another. CPython consumes the first iterator. Besides duplicating side effects, this can change results for stateful iterables. `sequence_fast` contains the same discard-and-reiterate pattern.

Checked clean in targeted runs:

- Hash consistency across `hash`, explicit `__hash__`, proxy keys, tuples, frozensets, and dict/set lookup.
- ABC negative-cache invalidation, registered descendants, lying `__class__`, registry-cycle rejection, and self-registration.
- Attribute-deletion finalizer timing with a live class dict view; a cyclic finalizer at exit reading intact globals.
- Package star imports with appended `__all__`, Latin-1 source decoding, and frozen `abc` resolution.
- Sampled built-in metadata, user-class `__subclasses__`, and `object.__subclasshook__`.

The abstract-property override probe and public `importlib` cache-function probe were cleanly refused, so neither is a finding. No full suites or `make check` were run.
