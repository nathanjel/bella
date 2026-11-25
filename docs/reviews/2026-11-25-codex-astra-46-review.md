Codex `gpt-6.2-astra` at low reasoning effort, 2026-11-25. Verbatim. Tag A46 in the review log. Range `25e2f67..0c25f5e`:
the import system's frames as CPython's (`0c25f5e`, Question 43, C-8-22), a step that changes what programs do broadly
(the author's rule of 2026-11-22), together with review A45's fixes, the answers to Questions 44 to 46 and E-06's refusal
at compile time, batched into one review as that rule says. Run non-interactively (standard input closed) in its own
worktree (`bella-r46`), the prompt worded as conformance, the step's residue (the frames CPython's import system enters and
leaves before a module's body runs) named as not to report. The run took five minutes (78,618 tokens). The session ran each
of the five programs again on both sides before any verdict, and swept the classes three of them belong to (review log, A46).

---

# A46 conformance review

Reviewed 25e2f67..0c25f5e against CPython 3.15.2.

## 1. The code object for _find_and_load omits its lock local

This is visible at normal recursion depth through the P1 names-and-counts attributes of a function's code object (dialect spec §4, E-02).

`prog.py`

```python
from importlib import _bootstrap
code = _bootstrap._find_and_load.__code__
print(code.co_nlocals, code.co_varnames)
```

CPython output

```text
6 ('name', 'import_', 'lazy_submodule', 'module', 'lock', 'message')
```

Compiled output

```text
5 ('name', 'import_', 'lazy_submodule', 'module', 'message')
```

CPython's `Lib/importlib/_bootstrap.py:1313` and `:1339` assign to the local variable `lock`. `Objects/codeobject.c:1688–1692` returns the fast-local names for `co_varnames`. Bella's single-threaded implementation omits the lock and exposes its own local-variable table.

## 2. A source loader's rejected name puts the wrong function and line in the traceback

`prog.py` imports an empty `sample.py` and queries the loader Python gave it.

```python
import traceback
import sample
try:
    sample.__loader__.get_filename("other")
except ImportError as error:
    for frame in traceback.extract_tb(error.__traceback__):
        print(frame.filename.split("/")[-1], frame.name, frame.lineno)
```

CPython output

```text
prog.py <module> 4
<frozen importlib._bootstrap_external> _check_name_wrapper 394
```

Compiled output

```text
prog.py <module> 4
<frozen importlib._bootstrap_external> get_filename 920
```

In CPython's `Lib/importlib/_bootstrap_external.py:918–920`, `@_check_name` decorates `FileLoader.get_filename`. The wrapper defined at line 390 raises at line 394 before entering the method. Bella folds that check into `FileLoader.get_filename` in `runtime/prelude/bootstrap.py`, so the traceback attributes the exception to the method.

## 3. An import skips a user-defined hash call that can reject the import

A string subclass is a valid module name. Its hash method can see the lock lookup using ordinary traceback extraction and raise there. This changes whether the import succeeds at the default recursion limit.

`prog.py`

```python
import traceback

class Name(str):
    def __hash__(self) -> int:
        for entry in traceback.extract_stack():
            if entry.name == "_get_module_lock":
                raise ValueError("hash during lock lookup")
        return super().__hash__()

def include() -> None:
    import sample

try:
    print(__import__(Name("sample")).answer)
except ValueError as error:
    print(error)
```

`sample.py`

```python
answer = 42
```

CPython output

```text
hash during lock lookup
```

Compiled output

```text
42
```

CPython's `Lib/importlib/_bootstrap.py:1338–1341` resolves the parents, obtains the module lock by name and acquires it. At line 438, `_get_module_lock` indexes the lock dictionary with that name. Lines 439–440 catch only `KeyError`, so the hash method's `ValueError` reaches the caller. Bella's `_find_and_load` skips the lock lookup. The uncalled `include` places the same source module in Bella's build closure.

## 4. A native module's default __dir__ lists its keys in a different order

`prog.py`

```python
import math
print([k for k in math.__dir__() if k in ("sin", "pi", "factorial", "sqrt")])
```

CPython output

```text
['sin', 'sqrt', 'pi', 'factorial']
```

Compiled output

```text
['pi', 'sin', 'sqrt', 'factorial']
```

The direct call observes the order that the built-in `dir(math)` subsequently sorts. CPython's `Objects/moduleobject.c:1572–1593` returns `PyDict_Keys(dict)` in the default case. In `Modules/mathmodule.c:3094–3096`, the method table lists `sin` before `sqrt`. The module execution slot then adds `pi` at line 3002 and `factorial` at line 3032. Bella's `module_dir_m` enumerates the runtime module's entries in their own insertion order.

## 5. ModuleSpec.has_location's getter combines a frozen filename with Bella's prelude line number

`prog.py` imports an empty `sample.py`. Reading the getter's code object exposes the wrong first line. Calling the getter on an object without the expected attribute exposes the wrong traceback line as well.

```python
import traceback
import sample
p = type(sample.__spec__).has_location
print(p.fget.__code__.co_firstlineno, p.fset.__code__.co_firstlineno)
try:
    p.fget(object())
except AttributeError as exc:
    for f in traceback.extract_tb(exc.__traceback__):
        print(f.filename.split("/")[-1], f.name, f.lineno)
```

CPython output

```text
637 641
prog.py <module> 6
<frozen importlib._bootstrap> has_location 639
```

Compiled output

```text
173 641
prog.py <module> 6
<frozen importlib._bootstrap> has_location 175
```

CPython's `Lib/importlib/_bootstrap.py:637–639` defines the getter and reads `self._set_fileattr` at 639. Lines 641–643 define the separately decorated setter. Both functions have the qualified name `ModuleSpec.has_location`. In `tools/bootstrap_frames.py`, `functions()` stores a single source span under each qualified name, so the setter overwrites the getter. The frontend gives the getter the frozen filename but finds only the setter's lines in the map.
