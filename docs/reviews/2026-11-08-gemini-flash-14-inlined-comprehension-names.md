gemini-3.8-flash-high through `agy` (print mode, sandbox), 2026-11-08, asked by the author. Verbatim. Tag G14 in the review
log. Its range is `3ea072a..46a5742`, the same as A14's; it ran in a detached checkout at `46a5742` with a shared, pre-built
`build/`, and could read the main checkout, where A14's fixes stood uncommitted, so its findings are against those (the
`co_cellvars` it quotes is the A14 #5 fix). A first run on 2026-11-07 hung after its tenth model call and was stopped the
next morning with nothing written; this is the second run (44 minutes).

---

### Review Range: `3ea072a..46a5742`

Reviewed the two commits:
- [`46a5742`](file:///home/nathan/workspaces/nth/bella/runtime/prelude/_json.py): `_json` (`scanstring`, escapes, surrogate pairs, `Scanner`, `Encoder`, error reporting, cyclic reference tracking, hook dispatch, subclasses, `frozendict`), and [`pipeline/closed_world.py`](file:///home/nathan/workspaces/nth/bella/pipeline/closed_world.py) (`search_roots` searching `PYTHONPATH`).
- [`83583fa`](file:///home/nathan/workspaces/nth/bella/runtime/src/types.cpp): code objects (`function.__code__` attributes and counts, `function.__closure__`, `del cell.cell_contents`, bytecode access stops by name per E-02), review fixes (`TextIOWrapper` cookies/re-init, `sys.stdout` flush, `LC_ALL`, lazy `TypeVar` bounds, `Template` sequence concatenation, `AST` identity repr, `TypeVarTuple` starred unpacking in thunk, unpack error messages), and `annotationlib` `_bella` hooks.

---

### Findings

#### Finding 1: Inlined comprehension cell variables order in `co_cellvars` is corrupted

- **Location**: [`pipeline/l2/resolve.py:412-419`](file:///home/nathan/workspaces/nth/bella/pipeline/l2/resolve.py#L412-L419) (`co_cellvars`)
- **Description**: Under PEP 709 in CPython, `co_cellvars` preserves the following strict order:
  1. Enclosing function's parameters that are cells (in parameter definition order).
  2. Inlined comprehensions' cell variables in the order the comprehensions appear in source (and for each comprehension, its cell variables in order of appearance).
  3. The enclosing function's other non-parameter cell variables, sorted alphabetically.

  In `pipeline/l2/resolve.py`, `co_cellvars(s)` places parameters first, but then collects all remaining cell variables—both from the enclosing function and from all inlined comprehensions—into a single set `others` and sorts them all together (`tuple(params + sorted(others))`). This causes cell variables belonging to inlined comprehensions to be sorted alphabetically and interleaved with the enclosing function's local cells, diverging from CPython.

- **Minimal Program**:
```python
def f(p):
    b = 1
    y = 2
    c1 = [(lambda: z) for z in range(2)]
    c2 = [(lambda: a) for a in range(2)]
    def inner():
        return p + b + y
    return inner, c1, c2

print(f.__code__.co_cellvars)
```
- **CPython 3.15.2 prints**:
```text
('p', 'z', 'a', 'b', 'y')
```
- **Compiled Bella prints**:
```text
('p', 'a', 'b', 'y', 'z')
```

---

#### Finding 2: Walrus expression in an inlined comprehension turns the target into a cell variable instead of a fast local

- **Location**: [`pipeline/l1/frontend.py:1724`](file:///home/nathan/workspaces/nth/bella/pipeline/l1/frontend.py#L1724) and [`pipeline/l2/resolve.py:108`](file:///home/nathan/workspaces/nth/bella/pipeline/l2/resolve.py#L108)
- **Description**: Under PEP 709 and PEP 572 in Python 3.12+, an assignment expression `(x := ...)` inside a list, set, or dict comprehension binds to a fast local in the enclosing function scope. It belongs in `co_varnames`, increments `co_nlocals`, and is not a cell variable unless an actual nested function/closure captures it.

  Bella desugars comprehensions into hoisted functions using `nonlocal x`. In `pipeline/l2/resolve.py`, encountering `nonlocal` in a nested scope unconditionally promotes `x` to `CELL` in the enclosing scope `s`. Because `x` is marked as `CELL`:
  1. `x` is omitted from `co_varnames`.
  2. `x` is falsely placed in `co_cellvars` even though no closure exists.
  3. `co_nlocals` is undercounted by 1.

- **Minimal Program**:
```python
def f():
    r = [(x := i * 2) for i in range(2)]
    return r, x

print("varnames:", f.__code__.co_varnames)
print("cellvars:", f.__code__.co_cellvars)
print("nlocals:", f.__code__.co_nlocals)
```
- **CPython 3.15.2 prints**:
```text
varnames: ('i', 'x', 'r')
cellvars: ()
nlocals: 3
```
- **Compiled Bella prints**:
```text
varnames: ('i', 'r')
cellvars: ('x',)
nlocals: 2
```

---

### Ranked List of Findings

1. **Finding 2** ([`pipeline/l1/frontend.py:1724`](file:///home/nathan/workspaces/nth/bella/pipeline/l1/frontend.py#L1724), [`pipeline/l2/resolve.py:108`](file:///home/nathan/workspaces/nth/bella/pipeline/l2/resolve.py#L108)): Walrus expression in an inlined comprehension misclassifies the target as `CELL` instead of `LOCAL`, omitting it from `co_varnames`, corrupting `co_nlocals`, and adding an spurious cell to `co_cellvars`.
2. **Finding 1** ([`pipeline/l2/resolve.py:412`](file:///home/nathan/workspaces/nth/bella/pipeline/l2/resolve.py#L412)): Inlined comprehension cell variables order in `co_cellvars` is corrupted by sorting all non-parameter cell variables together.

---

### Areas Exercised and Verified

- **`_json` Module** ([`runtime/prelude/_json.py`](file:///home/nathan/workspaces/nth/bella/runtime/prelude/_json.py)):
  - `scanstring`: Standard escapes (`\b`, `\f`, `\n`, `\r`, `\t`, `\"`, `\\`, `\/`), `\uXXXX` 4-digit hex validation, high/low surrogate pairs (`\uD800..\uDBFF` + `\uDC00..\uDFFF`), lone surrogates (`\uD800\uD800`), truncated surrogate escapes, out-of-bounds start indices, and `strict` mode control character rejection.
  - `make_scanner`: Parser hooks (`object_hook`, `object_pairs_hook`, `array_hook`, `parse_float`, `parse_int`, `parse_constant`), float vs integer discrimination, whitespace handling, nested array/dict parsing, and `StopIteration(idx)` error signaling.
  - `make_encoder`: Recursion and circular reference detection with `markers`, `default` fallback hook, fast paths for `encode_basestring` and `encode_basestring_ascii`, indent caching across indentation levels, key/item separators, key sorting (`sort_keys`), `skipkeys`, `allow_nan`, float and int subclass serialization without invoking subclass overrides, `dict` subclass iteration via `items()`, `frozendict` support, and exception note attachments (`when serializing ...`).
- **`pipeline/closed_world.py`**:
  - `search_roots` with multi-directory `PYTHONPATH`, resolving package origins and module imports relative to entrypoints.
- **Code Objects and Closures** ([`runtime/src/types.cpp`](file:///home/nathan/workspaces/nth/bella/runtime/src/types.cpp), [`pipeline/backend/cpp.py`](file:///home/nathan/workspaces/nth/bella/pipeline/backend/cpp.py), [`pipeline/l2/resolve.py`](file:///home/nathan/workspaces/nth/bella/pipeline/l2/resolve.py)):
  - Function code object attributes: `co_name`, `co_qualname`, `co_filename`, `co_firstlineno`, `co_argcount`, `co_posonlyargcount`, `co_kwonlyargcount`, `co_nlocals`, `co_varnames`, `co_cellvars`, `co_freevars`, `co_flags` (`CO_OPTIMIZED`, `CO_NEWLOCALS`, `CO_VARARGS`, `CO_VARKEYWORDS`, `CO_NESTED`, `CO_METHOD`, `CO_FUTURE_ANNOTATIONS`).
  - `function.__closure__` identity and cell tuples, `del cell.cell_contents` emptying cells, and assignment to `__code__` stopping by name.
- **Review 13 Regression Fixes**:
  - `TextIOWrapper.tell` cookie pack/unpack and `skip_bytes` clamp; `TextIOWrapper.__init__` reset behavior; `sys.stdout` replacement without `closed` and post-main module `flush_io`; `LC_ALL` locale coercion avoidance; unevaluated `TypeVar` bounds; `Template` and `deque` sequence concatenation; AST repr identity checks; `TypeVarTuple` starred default unpacks; and unpacking error formatting for tuples, lists, dicts, and non-iterables.
