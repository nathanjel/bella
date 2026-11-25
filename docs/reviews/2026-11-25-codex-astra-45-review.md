Codex `gpt-6.2-astra` at low reasoning effort, 2026-11-25. Verbatim. Tag A45 in the review log. Range `756222f..25e2f67`:
the program's module objects counted (`25e2f67`, Question 36, C-9-14, RL-933), a step that changes what programs do broadly
(the author's rule of 2026-11-22), together with C-3-82 (a mappingproxy of a class's dict), review A44's fixes, the C-9-13
split and the spec's wording commits, batched into one review as that rule says. Run non-interactively (standard input
closed) in its own worktree (`bella-r45`), the prompt worded as conformance, the known residue (a failed import's module
object dying when the import ends, Question 43) named as not to report. The session ran each of the five programs again
on both sides before any verdict (review log, A45).

---

# A45 conformance review, 756222f..25e2f67

All examples were run with the pinned CPython and with the exact build at HEAD. Finding 5 concerns an adjacent module-inspection path whose implementation predates the range.

## 1. ModuleType keeps a str subclass alive after its name is replaced

```python
from types import ModuleType

class Name(str):
    def __del__(self):
        print("name released")

m = ModuleType(Name("sample"))
m.__name__ = "renamed"
print("renamed")
del m
print("done")
```

CPython 3.15.2 stdout (exit 0)

```text
name released
renamed
done
```

Bella stdout (exit 0)

```text
renamed
name released
done
```

In CPython's `Objects/moduleobject.c:154–166`, `module_init_dict` stores the supplied name in the namespace and keeps a second reference in `md_name` only for an exact Unicode object. Replacing the dictionary entry therefore releases the last reference to this subclass instance. Bella's `module_init_m` also stores the subclass instance in `m->name`, so its finaliser waits until the module dies. The difference is observable while the module is still alive.

## 2. A class namespace reached through mappingproxy union disagrees with class attribute lookup

```python
class C:
    pass

class Capture:
    def __ror__(self, mapping):
        return mapping

d = C.__dict__ | Capture()
d["fresh"] = 42
print(C.__dict__.get("fresh"), getattr(C, "fresh", None))
```

CPython 3.15.2 stdout (exit 0)

```text
42 42
```

Bella stdout (exit 0)

```text
42 None
```

CPython's `Objects/typeobject.c:2079–2093` returns a proxy over the type dictionary. `Objects/descrobject.c:1065–1073` unwraps the proxy and dispatches the union on its underlying mapping, so the reflected operator receives the class dictionary itself. `Objects/typeobject.c:6193–6250` searches each MRO entry's dictionary for an attribute. This is the first lookup of the new attribute. Bella exposes the write through the proxy, but a lookup on the live class misses it.

## 3. Collecting a dataclass saves its generated method factory in gc.garbage

```python
import gc
import types
from dataclasses import dataclass

@dataclass
class Point:
    x: int

gc.collect()
gc.set_debug(gc.DEBUG_SAVEALL)
del Point
gc.collect()
print(sum(isinstance(o, types.FunctionType) and o.__name__ == "__create_fn__" for o in gc.garbage))
gc.set_debug(0)
```

CPython 3.15.2 stdout (exit 0)

```text
0
```

Bella stdout (exit 0)

```text
1
```

CPython's `Lib/dataclasses.py:497–500` creates a temporary local namespace, executes the generated definition in it, and calls the resulting factory. `Objects/funcobject.c:197–210` gives the new function references to its globals and builtins. The separate locals dictionary belongs to the execution of the definition. Bella's `hold_counted_globals` also retains that locals dictionary for the generated functions. It contains the factory, so the factory survives the preliminary collection and appears among the objects saved after deleting the class. `Python/gc.c:1095–1099` appends unreachable objects to the garbage list under DEBUG_SAVEALL. The probe checks for a particular generated function by type and name.

## 4. A function loses the builtins dictionary in effect when it was defined

```python
import weakref

class Marker:
    pass

marker = Marker()
watch = weakref.ref(marker)
__builtins__ = {"marker": marker}

def f():
    pass

del marker
del __builtins__
print("function alive", watch() is not None)
del f
print("function gone", watch() is not None)
```

CPython 3.15.2 stdout (exit 0)

```text
function alive True
function gone False
```

Bella stdout (exit 0)

```text
function alive False
function gone False
```

CPython's `Objects/funcobject.c:197–210` loads the builtins from the current globals and installs that reference as `func_builtins`. `Objects/dictobject.c:2695–2726` implements the lookup of `__builtins__`, and `Objects/funcobject.c:1187–1197` releases the reference when clearing the function. The probe rebinds a name in its own module. Deleting that binding leaves the function as the sole owner of the dictionary containing the marker.

## 5. Listing a module namespace calls a key's hash method again

```python
from types import ModuleType

class Key(str):
    def __hash__(self):
        print("hash")
        return 123

m = ModuleType("sample")
vars(m)[Key("public")] = 1
print("listing")
print("public" in dir(m))
```

CPython 3.15.2 stdout (exit 0)

```text
hash
listing
True
```

Bella stdout (exit 0)

```text
hash
listing
hash
True
```

CPython's `Objects/moduleobject.c:1572–1593` takes the existing namespace and returns its keys when it finds no custom `__dir__`. Bella's `module_dir_m` inserts the keys into a new dictionary first. That insertion runs user code during ordinary module inspection.
