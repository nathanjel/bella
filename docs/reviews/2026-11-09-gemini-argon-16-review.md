gemini-argon-4 (medium effort) through `agy`, 2026-11-09, asked by the author. Verbatim. Tag G16 in the review log. Its range is `2223023..726399f` (6 commits); it ran in its own worktree (`bella-g16`) at `726399f`, whose line numbers its citations carry. Four confirmed findings across staged compile, list subclasses, and importlib.

---

### Focus 1: Staged `compile()` ([`staged.cpp`](file:///home/nathan/workspaces/nth/bella-g16/runtime/src/staged.cpp), [`build.py`](file:///home/nathan/workspaces/nth/bella-g16/pipeline/build.py), [`cpp.py`](file:///home/nathan/workspaces/nth/bella-g16/pipeline/backend/cpp.py))

#### G16-01 — [`cpp.py:289-290`](file:///home/nathan/workspaces/nth/bella-g16/pipeline/backend/cpp.py#L289-L290), [`staged.cpp:287`](file:///home/nathan/workspaces/nth/bella-g16/runtime/src/staged.cpp#L287)
`pipeline/backend/cpp.py:289-290` hardcodes `if "annotations" in future: flags |= 0x1000000` when emitting `Code::flags`, ignoring all other future features (e.g. `barry_as_FLUFL` `0x400000`, `flags_of(future)`). When compiling a module with `from __future__ import barry_as_FLUFL`, the dry run stages the compile row with `flags = 0x400000`. At runtime, [`staged.cpp:287`](file:///home/nathan/workspaces/nth/bella-g16/runtime/src/staged.cpp#L287) computes `merged = flags | (dont_inherit || caller == nullptr ? 0 : caller->code->flags & FUTURE_MASK)`. Because `caller->code->flags` lacks `0x400000`, `merged` evaluates to 0, which fails to match `c.flags == 0x400000`. Bella refuses execution with `E-01: compile at ... of a text the dry run did not stage` (exit 70), while CPython executes the compiled code.

```python
from __future__ import barry_as_FLUFL
c = compile("1 <> 2", "<test>", "eval")
print(eval(c))
```
- **CPython 3.15.2**:
  ```text
  True
  ```
- **Bella (`726399f`)**:
  ```text
  bella: not implemented: E-01: compile at __main__:<module> of a text the dry run did not stage (spec section 8)
  ```
- **Severity**: High

---

#### G16-02 — [`build.py:186-187`](file:///home/nathan/workspaces/nth/bella-g16/pipeline/build.py#L186-L187) (`_MAY_STAGE`)
`pipeline/build.py:186-187` uses `r"|\b(?:" + "|".join(sorted(n for n in typing.__all__ if n[0].isupper())) + r")\[[^\]\n]*[\"']"` to detect subscripted typing expressions that stage a compile. The character class `[^\]\n]*` forbids newline characters. If a subscripted typing expression spans multiple lines (e.g. `Optional[\n    "int"\n]`), `_MAY_STAGE.search` returns `None`, skipping `_program_artefact` and the staging dry run. At runtime, evaluating the typing alias creates an `annotationlib.ForwardRef`, which calls `compile()` on the unstaged string, causing Bella to fail with exit code 70 instead of evaluating to the type alias.

```python
from typing import Optional
x = Optional[
    "int"
]
print(x)
```
- **CPython 3.15.2**:
  ```text
  ForwardRef('int') | None
  ```
- **Bella (`726399f`)**:
  ```text
  bella: not implemented: [P2+] annotationlib: a ForwardRef built at runtime from a text the build did not see needs it compiled at runtime (spec section 3, decision S-1)
  ```
- **Severity**: Medium

---

### Focus 3: `list` Subclasses ([`ops.cpp`](file:///home/nathan/workspaces/nth/bella-g16/runtime/src/ops.cpp))

#### G16-03 — [`ops.cpp:753`](file:///home/nathan/workspaces/nth/bella-g16/runtime/src/ops.cpp#L753) (`int_index_of`), [`ops.cpp:194`](file:///home/nathan/workspaces/nth/bella-g16/runtime/src/ops.cpp#L194), [`ops.cpp:1281`](file:///home/nathan/workspaces/nth/bella-g16/runtime/src/ops.cpp#L1281), [`ops.cpp:1304`](file:///home/nathan/workspaces/nth/bella-g16/runtime/src/ops.cpp#L1304)
In `runtime/src/ops.cpp:753`, [`int_index_of`](file:///home/nathan/workspaces/nth/bella-g16/runtime/src/ops.cpp#L750-L764) checks `if (is_heap_obj(v))` before attempting to call `__index__`. However, [`is_heap_obj`](file:///home/nathan/workspaces/nth/bella-g16/runtime/src/ops.cpp#L150) returns true only for `Kind::Instance` or `has_python_type(v)` (classes). Instances of `list` subclasses (`ListInstance`, added in commit `98afa38`) retain `Kind::List` and are identified by `is_subclass_instance(v)` (`has_attributes`). Because [`int_index_of`](file:///home/nathan/workspaces/nth/bella-g16/runtime/src/ops.cpp#L750-L764) does not check `is_subclass_instance(v)`, it ignores `__index__` on `list` (and `tuple`) subclasses, raising `TypeError: '...' object cannot be interpreted as an integer`. This breaks `int(L())`, sequence repetition (`[1] * L()`), sequence indexing (`[10, 20][L()]`), and slicing on `list` subclasses defining `__index__`.

```python
class L(list):
    def __index__(self):
        return 2

print([1] * L())
```
- **CPython 3.15.2**:
  ```text
  [1, 1]
  ```
- **Bella (`726399f`)**:
  ```text
  Traceback (most recent call last):
    File "prog.py", line 5, in <module>
  TypeError: 'list' object cannot be interpreted as an integer
  ```
- **Severity**: High

---

### Focus 4: `importlib` ([`call.cpp`](file:///home/nathan/workspaces/nth/bella-g16/runtime/src/call.cpp), [`bootstrap.py`](file:///home/nathan/workspaces/nth/bella-g16/runtime/prelude/bootstrap.py))

#### G16-04 — [`call.cpp:2580-2586`](file:///home/nathan/workspaces/nth/bella-g16/runtime/src/call.cpp#L2580-L2586)
In `runtime/src/call.cpp:2580-2586`, `_frozen_importlib` and `_frozen_importlib_external` (and their aliases `importlib._bootstrap` and `importlib._bootstrap_external`) are inserted into `sys.modules`, but their `__spec__` attributes are left unset (`None`). In CPython 3.15.2, frozen bootstrap modules in `sys.modules` have `__spec__ = ModuleSpec(name=..., loader=FrozenImporter, origin='frozen')`. When [`importlib.util.find_spec`](file:///home/nathan/workspaces/nth/bella-g16/runtime/prelude/bootstrap_external.py) is called with `"_frozen_importlib"` or `"importlib._bootstrap"`, it inspects the existing module in `sys.modules`, finds `__spec__ is None`, and raises `ValueError: _frozen_importlib.__spec__ is None` instead of returning the module specification.

```python
import importlib.util
print(importlib.util.find_spec("_frozen_importlib"))
```
- **CPython 3.15.2**:
  ```text
  ModuleSpec(name='_frozen_importlib', loader=<class '_frozen_importlib.FrozenImporter'>, origin='frozen')
  ```
- **Bella (`726399f`)**:
  ```text
  Traceback (most recent call last):
    File "prog.py", line 2, in <module>
    File "<frozen importlib.util>", line 110, in find_spec
  ValueError: _frozen_importlib.__spec__ is None
  ```
- **Severity**: Medium
