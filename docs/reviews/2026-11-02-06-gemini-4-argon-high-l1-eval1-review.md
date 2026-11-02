# Bella L1 Frontend & `eval1` Closure Review (`3d4e428..58bb34b`, Task 4 Steps A1–B & P-1..P-3)

- **Date:** 2026-11-02
- **Reviewer:** `gemini-4-argon-high`
- **Sequence:** 06
- **Commit Range Reviewed:** `3d4e428..58bb34b` (`3d4e428f60ea57122298ed7ffb6fff6e1db637fb..58bb34b7b6b2fdce87e2972b87f38c80cbc0aa7a`)

---

## 1. Executive Summary

The 11 commits in `3d4e428..58bb34b` take Gate 0 Task 4 from the compile-scope measurement (`D-10`) through a full L1 frontend and `eval1` runtime capable of running all three phase-1 target programs (`cli_easy_slugs`, `service_easy_tokens`, `data_easy_sales`) with their entire standard-library closures and staged artefacts:

1. **Compile-Scope Measurement & Decisions `P-1`..`P-3` (`4ade944`, `89d4198`, `58bb34b`):** [`tools/scope.py`](file:///home/nathan/workspaces/nth/bella/tools/scope.py) and [`docs/measurements.md`](file:///home/nathan/workspaces/nth/bella/docs/measurements.md) measure executed vs. closure code objects (`7.0%`–`11.2%` on `cli_easy_slugs`) and construct frequencies across the three targets. Decision **P-1** compiles the whole closure (with unlowered statements becoming uncatchable runtime refusals); **P-2** adds [`runtime/shims/_collections_abc.py`](file:///home/nathan/workspaces/nth/bella/runtime/shims/_collections_abc.py) importing the four probed runtime types from `_types` (`C-7-18`); **P-3** relaxes `wf1`'s compile-time `NameError` to runtime global lookup in library modules (spec v0.12 §8).
2. **L1 Frontend Desugarings onto a Small Core (`11b4f04`, `56565c0`, `51c380b`, `e95e61f`, `7626094`, `606d54e`, `14db683`):** [`pipeline/l1/frontend.py`](file:///home/nathan/workspaces/nth/bella/pipeline/l1/frontend.py) and [`pipeline/l1/grammar.py`](file:///home/nathan/workspaces/nth/bella/pipeline/l1/grammar.py) lower Python 3.15 constructs into L1 via explicit AST passes (`desugar-annotations`, `desugar-type-params`, `desugar-class-body`, `desugar-private-names`, `desugar-imports`, `desugar-several-targets`, `desugar-match`, `desugar-chained-compare`, `desugar-with`, `desugar-listcomp`, `desugar-fstring`, `desugar-decorators`, `to-l1`), backed by compiled Python runtime helpers [`runtime/prelude/build_class.py`](file:///home/nathan/workspaces/nth/bella/runtime/prelude/build_class.py) and [`runtime/prelude/match.py`](file:///home/nathan/workspaces/nth/bella/runtime/prelude/match.py) and inspected via [`pipeline/l1/pretty.py`](file:///home/nathan/workspaces/nth/bella/pipeline/l1/pretty.py).
3. **`eval1` Reference Semantics, Module System & Staged Texts (`51c380b`, `fee0242`):** [`pipeline/l1/eval1.py`](file:///home/nathan/workspaces/nth/bella/pipeline/l1/eval1.py), [`pipeline/l1/modules.py`](file:///home/nathan/workspaces/nth/bella/pipeline/l1/modules.py), [`pipeline/l1/staged.py`](file:///home/nathan/workspaces/nth/bella/pipeline/l1/staged.py), and [`pipeline/l1/run.py`](file:///home/nathan/workspaces/nth/bella/pipeline/l1/run.py) execute `74` of `80` conformance cases ([`conformance/eval1-baseline.txt`](file:///home/nathan/workspaces/nth/bella/conformance/eval1-baseline.txt)) and all three phase-1 targets in `--modules closure` mode with `0` unlowered closure modules.

**Overall Assessment:** The architectural direction—lowering surface Python via composable AST passes and pure-Python prelude modules (`build_class.py`, `match.py`) onto a compact L1 grammar—is clean, auditable, and avoids turning Bella into a copy of CPython's bytecode VM. In particular, the C-source fidelity on `initialize_locals` argument binding, `codegen_dict`'s 15-pair sub-dict flushing, `starunpack_helper`'s 30-item threshold, `_PyDict_MergeUniq`, and `_PyEval_UnpackIterableStackRef` is exceptionally thorough.

Differential testing of the new passes, prelude helpers, `wf1` relaxations, and `eval1` runtime against the pinned CPython 3.15.2 uncovered **seven groups of concrete bugs** (excluding all known open items in [`TODO.md`](file:///home/nathan/workspaces/nth/bella/TODO.md)). Section 2 details each finding with a minimal reproduction against CPython 3.15.2 and a concrete fix.

---

## 2. Technical Findings & Semantic Divergences from CPython 3.15.2

### 2.1 [High / Pass Ordering, PEP 563 & PEP 649] [`frontend.py:1696-1724`](file:///home/nathan/workspaces/nth/bella/pipeline/l1/frontend.py#L1696-L1724) (`_ToL1.annotate`) vs. [`frontend.py:1316-1321`](file:///home/nathan/workspaces/nth/bella/pipeline/l1/frontend.py#L1316-L1321) (`_Comprehensions.visit_FunctionDef`): Lowering function annotations in `to-l1` corrupts PEP 563 annotation strings and crashes on comprehensions in PEP 649 annotations

- **Location:** [`pipeline/l1/frontend.py:1696-1724`](file:///home/nathan/workspaces/nth/bella/pipeline/l1/frontend.py#L1696-L1724) (`_ToL1.annotate`) and [`pipeline/l1/frontend.py:1316-1321`](file:///home/nathan/workspaces/nth/bella/pipeline/l1/frontend.py#L1316-L1321) (`_Comprehensions.visit_FunctionDef`)
- **Problem:** Module and class annotations are lowered in `desugar-annotations` (the *first* pass in `FRONTEND_PASSES`), whereas function parameter and return annotations are left on `ast.FunctionDef` until `_ToL1.annotate` in `to-l1` (the *last* pass in `FRONTEND_PASSES`). This causes two distinct bugs:
  1. **PEP 563 (`from __future__ import annotations`) unparses already-desugared ASTs:** When `self.future_annotations` is `True`, `_ToL1.annotate` calls `ast.unparse(e)` at line 1713 *after* `desugar-private-names`, `desugar-chained-compare`, and `desugar-fstring` have mutated `e` in-place. As a result, `fn.__annotations__` leaks mangled private names, synthetic `_cmpN` walrus bindings, and `bella:format` intrinsics instead of the original source text.
  2. **PEP 649 function annotations containing comprehensions crash `to-l1`:** `_Comprehensions.visit_FunctionDef` (lines 1316–1321) visits `decorator_list`, `defaults`, and `kw_defaults`, but never visits parameter annotations (`p.annotation`) or `node.returns`. When `_ToL1.annotate` calls `self.expr(e)` on an annotation containing a comprehension, it raises `Unsupported: expression ListComp`.
- **Reproduction:**
  ```python
  # (a) PEP 563 function annotations
  from __future__ import annotations
  class C:
      def f(self, a: __Priv, b: f"{int}", c: 1 < 2 < 3) -> __Priv:
          pass
  print(C.f.__annotations__)
  # CPython 3.15.2: {'a': '__Priv', 'b': "f'{int}'", 'c': '1 < 2 < 3', 'return': '__Priv'}
  # eval1:          {'a': '_C__Priv', 'b': "''.join((bella:format(int, ''),))", 'c': '1 < (_cmp2 := 2) and _cmp2 < 3', 'return': '_C__Priv'}

  # (b) PEP 649 comprehension in function annotation
  def g(x: [t for t in (int,)]) -> int:
      return 1
  # CPython 3.15.2: g.__annotations__ == {'x': [<class 'int'>], 'return': <class 'int'>}
  # eval1:          Unsupported: expression ListComp (line 1)
  ```
- **Recommendation:** Build a function's `__annotate__` `ast.FunctionDef` in `desugar-annotations` (`_Annotations`)—before `desugar-private-names`, `desugar-chained-compare`, `desugar-listcomp`, and `desugar-fstring` run—or record the unparsed PEP 563 strings in `desugar-annotations` and run `_hoist` on `__annotate__`'s body.

---

### 2.2 [High / Wrong Output & Crash] [`frontend.py:216-259, 287-290`](file:///home/nathan/workspaces/nth/bella/pipeline/l1/frontend.py#L216-L259) (`_Annotations` & `_declare`): Four bugs in value-less annotated assignments (`AnnAssign` with `value is None`)

- **Location:** [`pipeline/l1/frontend.py:216-259`](file:///home/nathan/workspaces/nth/bella/pipeline/l1/frontend.py#L216-L259) (`_Annotations.function_body`, `_Annotations.annassign`) and [`pipeline/l1/frontend.py:287-290`](file:///home/nathan/workspaces/nth/bella/pipeline/l1/frontend.py#L287-L290) (`_declare`)
- **Problem:**
  1. **`_declare` hides private names from `desugar-private-names`:** `_declare(s)` emits ` __bella_intrinsic_declare(ast.Constant(s.target.id))`. Because the identifier is stored inside an `ast.Constant(str)` rather than an `ast.Name`, `_PrivateNames` ([`frontend.py:747-786`](file:///home/nathan/workspaces/nth/bella/pipeline/l1/frontend.py#L747-L786)) never mangles it. Inside `class C:`, `__x: int` declares `"__x"` instead of `"_C__x"`, so a method `def f(self): __x: int; return __x` either fails at compile time (`WellFormednessError: name '_C__x' is bound nowhere`) or, if `_C__x` exists at module scope, silently returns the global `_C__x` instead of raising `UnboundLocalError`.
  2. **`AssertionError` crash on `self.a: int` or `d[k]: int` in a function body:** `_Annotations.function_body` (line 221–222) calls `_declare(s)` whenever `s.value is None`, without checking `isinstance(s.target, ast.Name)`. Annotating an attribute or subscript without a value inside a method (`self.a: int`) crashes the compiler with `AssertionError` at line 288 (`assert isinstance(s.target, ast.Name)`).
  3. **Parenthesized `(x): int` (`s.simple == 0`) in a function body:** `_Annotations.function_body` does not check `s.simple`, so `(x): int` inside a function emits `_declare(s)` and makes `x` local (raising `UnboundLocalError`), whereas in CPython (`Python/symtable.c`), `(x): int` has `s.simple == 0` and does *not* bind `x` as a local variable.
  4. **Dropped target side effects on `obj().a: int` and `obj()[idx()]: int`:** In CPython (`Python/codegen.c:codegen_annassign`), when `s.value is None` and `s.target` is an `ast.Attribute` or `ast.Subscript`, CPython still evaluates `s.target.value` (and `s.target.slice` for `Subscript`) for side effects. `_Annotations.annassign` (lines 244–259) drops them completely.
- **Reproduction:**
  ```python
  # 1. Private annotated local without value reads global instead of raising UnboundLocalError
  _C__x = "global_leak"
  class C:
      def f(self):
          __x: int
          return __x
  # CPython 3.15.2: UnboundLocalError: cannot access local variable '_C__x' where it is not associated with a value
  # eval1:          returns 'global_leak'

  # 2. Attribute annotation without value in method crashes compiler
  class D:
      def f(self):
          self.a: int
  # CPython 3.15.2: ok (D.__static_attributes__ == ())
  # eval1:          AssertionError in _declare (frontend.py:288)

  # 3 & 4. Non-simple target (x): int and side-effecting target obj()[idx()]: int
  x = "global_x"
  def h():
      (x): int
      return x
  # CPython 3.15.2: 'global_x'
  # eval1:          UnboundLocalError
  ```
- **Recommendation:**
  - In `_declare` (or `_PrivateNames`), mangle the declared name with the enclosing class (or pass an `ast.Name(id=s.target.id, ctx=ast.Store())` to `%declare` so `_PrivateNames` mangles it automatically).
  - In both `function_body` and `annassign`, when `s.value is None`: emit `_declare(s)` only when `s.simple and isinstance(s.target, ast.Name)`; when `isinstance(s.target, ast.Attribute)`, emit `ast.Expr(s.target.value)`; when `isinstance(s.target, ast.Subscript)`, emit `[ast.Expr(s.target.value), ast.Expr(s.target.slice)]`.

---

### 2.3 [High / PEP 695 & Class Scopes] Three bugs in [`frontend.py:307-454`](file:///home/nathan/workspaces/nth/bella/pipeline/l1/frontend.py#L307-L454) (`_TypeParams`), [`wf.py:272-278`](file:///home/nathan/workspaces/nth/bella/pipeline/l1/wf.py#L272-L278), and [`eval1.py:1371-1390`](file:///home/nathan/workspaces/nth/bella/pipeline/l1/eval1.py#L1371-L1390) (`_pep695`)

- **Location:** [`pipeline/l1/wf.py:210-221, 272-278`](file:///home/nathan/workspaces/nth/bella/pipeline/l1/wf.py#L272-L278), [`pipeline/l1/frontend.py:348-356, 397-449, 747-757`](file:///home/nathan/workspaces/nth/bella/pipeline/l1/frontend.py#L397-L449), and [`pipeline/l1/eval1.py:1371-1390`](file:///home/nathan/workspaces/nth/bella/pipeline/l1/eval1.py#L1371-L1390)
- **Problem:**
  1. **`wf.py` rejects generic nested classes whose base classes or keywords reference attributes of the enclosing class (`class Outer: class Base: pass; class Inner[T](Base): pass`):** `_TypeParams` wraps `class Inner[T](Base):` in `def <generic parameters of Inner>():` with `classdict=True` and `annotation=False`. At runtime, `eval1.py:538` honours `classdict=True` and resolves `Base` in `Outer`'s class namespace (`LOAD_FROM_DICT_OR_GLOBALS`). However, `wf.py:210-221` and `272-278` ignore `s.classdict` on `L.FunctionDef` and unconditionally skip `s.bound` when `s.is_class` is `True`, raising `WellFormednessError: line 5: name 'Base' is bound nowhere in its scope chain`.
  2. **Private type parameters on generic classes (`class Inner[__T]: v = __T`):** In CPython 3.15.2 (`Python/symtable.c`), the type-parameter scope `<generic parameters of Inner>` of a generic class `Inner` sets `st_private = "Inner"` when binding its type parameters, so `[__T]` is bound as `_Inner__T` (while the `TypeVar`'s `__name__` remains `"__T"`). In `frontend.py`, `_TypeParams` places `(__T,) = _params` in `<generic parameters of Inner>` *outside* `class Inner:`; when `_PrivateNames` runs, `self.private` is not `"Inner"` yet, so the binding remains `__T` (or `_Outer__T` if nested) while uses inside `Inner`'s body and methods are mangled to `_Inner__T`, causing `WellFormednessError: name '_Inner__T' is bound nowhere`.
  3. **Wrong `repr()` on PEP 695 `type` aliases defined inside classes (`class Outer: type Alias = int`):** In CPython 3.15.2, a `TypeAliasType` created inside a class body has its qualified name set (`repr(Outer.Alias) == 'Outer.Alias'`). `_pep695` ([`eval1.py:1384`](file:///home/nathan/workspaces/nth/bella/pipeline/l1/eval1.py#L1384)) compiles `f"type {name} = __bella_v__()"` at module level in `ns`, so `repr(Outer.Alias)` is `'Alias'` instead of `'Outer.Alias'`.
- **Reproduction:**
  ```python
  # 1. Generic nested class inheriting from an enclosing class attribute
  class Outer:
      class Base: pass
      class Inner[T](Base): pass
  # CPython 3.15.2: Outer.Inner.__bases__ == (<class 'Outer.Base'>, <class 'typing.Generic'>)
  # eval1:          WellFormednessError: line 4: name 'Base' is bound nowhere in its scope chain

  # 2. Generic class with private type parameter
  class Box[__T]:
      v = __T
  # CPython 3.15.2: Box.v is Box.__type_params__[0] (__T)
  # eval1:          WellFormednessError: line 2: name '_Box__T' is bound nowhere in its scope chain

  # 3. TypeAlias inside a class
  class C:
      type Alias = int
  print(repr(C.Alias))
  # CPython 3.15.2: C.Alias
  # eval1:          Alias
  ```
- **Recommendation:**
  - In [`wf.py`](file:///home/nathan/workspaces/nth/bella/pipeline/l1/wf.py#L210-L221), record `classdict=s.classdict` on `_Scope` for `L.FunctionDef`, and in [`wf.py:273`](file:///home/nathan/workspaces/nth/bella/pipeline/l1/wf.py#L273) allow a scope with `scope.classdict` to resolve names in the nearest enclosing `s.is_class` scope's `s.bound`.
  - On `<generic parameters of Class>` (or in `_TypeParams.generic` for `ast.ClassDef`), mangle the class's type-parameter bindings (and uses of those type parameters in the class's bases/keywords) with `node.name`.
  - For `typealias`, pass the enclosing class's `qualname` (if any) into `_pep695` so the synthetic `type` statement is nested inside `class` blocks matching the qualname parts (or construct it with the qualified name).

---

### 2.4 [High / Comprehensions, Walrus & Lambdas] Three bugs in [`frontend.py:1293-1411`](file:///home/nathan/workspaces/nth/bella/pipeline/l1/frontend.py#L1293-L1411) (`_Comprehensions`) and [`eval1.py:397-403`](file:///home/nathan/workspaces/nth/bella/pipeline/l1/eval1.py#L397-L403) (`_local_names`)

- **Location:** [`pipeline/l1/eval1.py:397-403`](file:///home/nathan/workspaces/nth/bella/pipeline/l1/eval1.py#L397-L403) (`_local_names`), [`pipeline/l1/frontend.py:1354-1411`](file:///home/nathan/workspaces/nth/bella/pipeline/l1/frontend.py#L1354-L1411) (`_Comprehensions.comprehension`)
- **Problem:**
  1. **Walrus `:=` in a comprehension inside a `lambda` fails at runtime with `SyntaxError`:** In [`wf.py:251-255`](file:///home/nathan/workspaces/nth/bella/pipeline/l1/wf.py#L251-L255), `L.Lambda` collects local bindings from both `_walrus(e.body, inner.bound)` and `_bound_in(e.prelude, inner.bound)`. In [`eval1.py:399-401`](file:///home/nathan/workspaces/nth/bella/pipeline/l1/eval1.py#L399-L401), `_local_names(f)` only calls `_walrus(f.body, out)` and omits `_bound_in(f.prelude, out)`. Because `visit_Lambda` hoists the comprehension helper `_comp0` (with `enclosing_binds={"y"}` and `nonlocal y`) into `f.prelude`, `y` is not in the lambda's `scope.locals_`, and calling the lambda raises `SyntaxError: no binding for nonlocal 'y' found`.
  2. **Walrus `:=` in a comprehension inside a function that declares the target `global` fails at runtime with `SyntaxError`:** In [`frontend.py:1387`](file:///home/nathan/workspaces/nth/bella/pipeline/l1/frontend.py#L1387), `_Comprehensions.comprehension` always emits `ast.Nonlocal(names=bound_outside)` and sets `fn.bella_enclosing_binds = bound_outside` whenever `self.scope == "function"`. If the containing function declared `global gx`, `_local_names` on the containing function subtracts `f.globals` (`gx`), so `_comp0`'s `nonlocal gx` fails in `_enclosing_binding` with `SyntaxError: no binding for nonlocal 'gx' found`.
  3. **`yield` inside a comprehension (`[(yield x) for x in (1, 2)]`) is not rejected as `SyntaxError`:** Because `ast.parse` accepts `yield` inside a comprehension and leaves rejection to `symtable`/`codegen`, `_Comprehensions` hoists `(yield x)` into `_comp0`, which `_ToL1` turns into a generator function returning an unconsumed `<generator object _comp0>` while the enclosing function `def g():` becomes a regular function instead of raising `SyntaxError: 'yield' inside list comprehension`.
- **Reproduction:**
  ```python
  # 1. Walrus in comprehension inside lambda
  fn = lambda: ([(y := i) for i in (1, 2, 3)], y)
  print(fn())
  # CPython 3.15.2: ([1, 2, 3], 3)
  # eval1:          SyntaxError: no binding for nonlocal 'y' found

  # 2. Walrus in comprehension targeting a global in a function
  def f():
      global gx
      [gx := i for i in (1, 2, 3)]
  f()
  # CPython 3.15.2: gx == 3
  # eval1:          SyntaxError: no binding for nonlocal 'gx' found

  # 3. yield inside comprehension
  def g():
      return [(yield x) for x in (1, 2)]
  # CPython 3.15.2: SyntaxError: 'yield' inside list comprehension
  # eval1:          g() returns <generator object g.<locals>._comp0>
  ```
- **Recommendation:**
  - In [`eval1.py:399-401`](file:///home/nathan/workspaces/nth/bella/pipeline/l1/eval1.py#L399-L401), add `_bound_in(f.prelude, out)` for `L.Lambda` (matching [`wf.py:254`](file:///home/nathan/workspaces/nth/bella/pipeline/l1/wf.py#L254)).
  - In `_Comprehensions`, pass the enclosing function's `global` declarations down (or check `_enclosing_binding` against `s.globals_` in `eval1.py`), emitting `ast.Global` for names declared `global` in the containing function and `ast.Nonlocal` for the rest.
  - In `_Comprehensions.comprehension`, check if any expression in `parts` or `outer_iter` contains an `ast.Yield` or `ast.YieldFrom` (not inside a nested `Lambda`) and raise `SyntaxError(f"'yield' inside {kind_label} (line {node.lineno})")`.

---

### 2.5 [Medium / Generators] [`eval1.py:791-804, 853, 955-973, 1020-1029`](file:///home/nathan/workspaces/nth/bella/pipeline/l1/eval1.py#L955-L973) (`gexpr`, `gstmt`, `run_generator`): Artificial `Refused` on `yield` inside f-strings, t-strings, slices, comprehension iterables, and chained comparisons; missing `self.frames` tracking in generators

- **Location:** [`pipeline/l1/eval1.py:955-973`](file:///home/nathan/workspaces/nth/bella/pipeline/l1/eval1.py#L955-L973) (`Interpreter.gexpr`), [`pipeline/l1/eval1.py:853`](file:///home/nathan/workspaces/nth/bella/pipeline/l1/eval1.py#L853) (`Interpreter.gstmt`), and [`pipeline/l1/eval1.py:791-804, 1020-1029`](file:///home/nathan/workspaces/nth/bella/pipeline/l1/eval1.py#L1020-L1029) (`run_generator`, `call`)
- **Problem:**
  1. **`gexpr` rejects all `L.Intrinsic` calls and `__bind__` calls containing a `yield`:** At lines 955–957, `gexpr` guards `L.Call` with `not isinstance(e.func, L.Intrinsic) and not (isinstance(e.func, L.Name) and e.func.id == "__bind__")`. Because the frontend desugars f-strings (`%format`, `%str`, `%repr`, `%ascii`), t-strings (`%template`, `%interpolation`), slices (`%slice`), comprehension outer iterables (`%iter`), and chained comparisons (`__bind__`) into intrinsic or `__bind__` calls, any `yield` inside those constructs raises `L.Refused: a yield inside Call is not lowered`.
  2. **`gstmt` for `L.For` omits `_has_yield_target(s.target)`:** Unlike `L.Assign` (line 820), `L.For` (line 853) calls `self.assign(s.target, v, scope)` directly without checking `_has_yield_target(s.target)`, crashing with `TypeError: unknown expression Yield` on `for a[(yield 1)] in xs:`.
  3. **`self.frames` is not updated while a generator steps:** In `Interpreter.call` (lines 1020–1023), generator functions return `self.run_generator(node, scope)` before `self.frames.append((module, node.qualname))`, and `run_generator` never pushes `(module, node.qualname)` onto `self.frames`. Consequently, `self.site()` and `self.caller_flags()` inside a running generator report the caller of `next(gen)` rather than the generator's own `(module, qualname)` and `__future__` flags.
- **Reproduction:**
  ```python
  def g1():
      yield f"val={(yield 1)!r}"
  def g2():
      return [10, 20, 30][(yield 1):]
  def g3():
      return [x * 2 for x in (yield "iter")]
  def g4():
      return 1 < (yield "mid") < 5
  # CPython 3.15.2: all four generators run normally
  # eval1:          all four fail with Refused: a yield inside Call is not lowered
  ```
- **Recommendation:**
  - In `gexpr` ([`eval1.py:955-966`](file:///home/nathan/workspaces/nth/bella/pipeline/l1/eval1.py#L955-L966)), handle `__bind__` (`value = yield from self.gexpr(e.args[1], scope); self.store(name.value, value, scope); return value`) and allow `L.Intrinsic` calls (evaluating `fn = self.expr(e.func, scope)` and `args` via `yield from self.gexpr(a, scope)`).
  - Check `if _has_yield_target(s.target): raise L.Refused(...)` in `gstmt` for `L.For`.
  - Push `(module, node.qualname)` onto `self.frames` while stepping a generator (or around non-yield segments in `run_generator`).

---

### 2.6 [Medium / `match` & `build_class` Exactness] Four divergences in [`frontend.py:989-1003`](file:///home/nathan/workspaces/nth/bella/pipeline/l1/frontend.py#L989-L1003), [`runtime/prelude/match.py`](file:///home/nathan/workspaces/nth/bella/runtime/prelude/match.py), and [`runtime/prelude/build_class.py`](file:///home/nathan/workspaces/nth/bella/runtime/prelude/build_class.py)

- **Location:** [`pipeline/l1/frontend.py:989-1003`](file:///home/nathan/workspaces/nth/bella/pipeline/l1/frontend.py#L989-L1003) (`_pattern_names`), [`runtime/prelude/match.py:52-58, 86`](file:///home/nathan/workspaces/nth/bella/runtime/prelude/match.py#L52-L58), and [`runtime/prelude/build_class.py:46, 94`](file:///home/nathan/workspaces/nth/bella/runtime/prelude/build_class.py#L46)
- **Problem:**
  1. **Negative and complex literal keys in `MatchMapping` (`case {-1: a, 1+2j: b}:`) raise a false `SyntaxError`:** `_pattern_names` ([`frontend.py:992-997`](file:///home/nathan/workspaces/nth/bella/pipeline/l1/frontend.py#L992-L997)) checks `if isinstance(k, ast.Constant): ... elif not isinstance(k, ast.Attribute): raise SyntaxError(...)`. In Python's AST, negative number literals (`-1`) are `ast.UnaryOp(op=ast.USub(), operand=ast.Constant(1))` and complex literals (`1+2j`) are `ast.BinOp(op=ast.Add()/ast.Sub(), ...)`, so valid mapping patterns with negative or complex keys are rejected with `SyntaxError: mapping pattern keys may only match literals and attribute lookups`.
  2. **Duplicate keyword attributes in `MatchClass` (`case Point(x=1, x=1):`) are not rejected at compile time or runtime:** `_pattern_names` ([`frontend.py:1001-1003`](file:///home/nathan/workspaces/nth/bella/pipeline/l1/frontend.py#L1001-L1003)) does not check `q.kwd_attrs` for duplicates (CPython's `compiler_pattern_class` raises `SyntaxError: attribute name repeated in class pattern: x`), and `match_class` ([`runtime/prelude/match.py:86`](file:///home/nathan/workspaces/nth/bella/runtime/prelude/match.py#L86)) initializes `seen = set() if nargs > 0 and nattrs > 1 else None`, so when `nargs == 0`, duplicate keyword attributes silently match.
  3. **`mapping_rest` ([`runtime/prelude/match.py:55`](file:///home/nathan/workspaces/nth/bella/runtime/prelude/match.py#L55)) uses `rest.update(subject)` instead of `DICT_UPDATE`:** For a `collections.abc.Mapping.register` class that implements `__iter__` yielding `(k, v)` pairs but lacks `.keys()`, `match WeirdMap(): case {**rest}:` raises `TypeError: 'WeirdMap' object is not a mapping` in CPython (`DICT_UPDATE` calls `PyDict_Update` -> `PyDict_Merge`), whereas `rest.update(subject)` in `match.py` falls back to sequence-of-pairs iteration and succeeds with `{'a': 1}`.
  4. **`build_class.py` ([`runtime/prelude/build_class.py:46, 94`](file:///home/nathan/workspaces/nth/bella/runtime/prelude/build_class.py#L46)) uses `getattr(..., None)` instead of a sentinel for `__mro_entries__` and `__prepare__`:** In CPython (`Python/bltinmodule.c`), `PyObject_GetOptionalAttr` distinguishes an absent attribute (`AttributeError`) from an attribute whose value is `None`. When a base has `__mro_entries__ = None` or a metaclass has `__prepare__ = None`, CPython attempts to call `None` and raises `TypeError: 'NoneType' object is not callable`, whereas `build_class.py` treats `None` as absent.
- **Reproduction:**
  ```python
  # 1. Negative and complex keys in mapping pattern
  match {-1: "neg", 1+2j: "cplx"}:
      case {-1: a, 1+2j: b}:
          print(a, b)
  # CPython 3.15.2: neg cplx
  # eval1:          SyntaxError: mapping pattern keys may only match literals and attribute lookups

  # 2. Duplicate keyword attribute in class pattern
  class Point: x = 1
  match Point():
      case Point(x=1, x=1):
          print("matched")
  # CPython 3.15.2: SyntaxError: attribute name repeated in class pattern: x
  # eval1:          matched

  # 4. Metaclass with __prepare__ = None
  class Meta(type): __prepare__ = None
  class C(metaclass=Meta): pass
  # CPython 3.15.2: TypeError: 'NoneType' object is not callable
  # eval1:          succeeds silently
  ```
- **Recommendation:**
  - In `_pattern_names` ([`frontend.py:990-1003`](file:///home/nathan/workspaces/nth/bella/pipeline/l1/frontend.py#L990-L1003)), evaluate constant literal keys via `ast.literal_eval(k)` when `not isinstance(k, ast.Attribute)` for duplicate checking, and check `q.kwd_attrs` on `ast.MatchClass` for duplicate attribute names (`SyntaxError(f"attribute name repeated in class pattern: {attr} (line {q.lineno})")`).
  - In [`runtime/prelude/match.py:55`](file:///home/nathan/workspaces/nth/bella/runtime/prelude/match.py#L55), use the same `.keys()` merge logic as `_dict_update` in `eval1.py:1475-1491`.
  - In [`runtime/prelude/build_class.py:46, 94`](file:///home/nathan/workspaces/nth/bella/runtime/prelude/build_class.py#L46), use a module-level `_absent = object()` sentinel in `getattr(base, "__mro_entries__", _absent)` and `getattr(meta, "__prepare__", _absent)`.

---

### 2.7 [Medium / Calls, Imports, `wf1` Relaxations & Closure Pre-lowering] Four bugs across [`eval1.py:1206-1226`](file:///home/nathan/workspaces/nth/bella/pipeline/l1/eval1.py#L1206-L1226), [`frontend.py:832-890`](file:///home/nathan/workspaces/nth/bella/pipeline/l1/frontend.py#L832-L890), [`wf.py:105-117, 199, 211`](file:///home/nathan/workspaces/nth/bella/pipeline/l1/wf.py#L105-L117), and [`modules.py:84-94`](file:///home/nathan/workspaces/nth/bella/pipeline/l1/modules.py#L84-L94)

- **Location:** [`pipeline/l1/eval1.py:518-572, 1206-1226`](file:///home/nathan/workspaces/nth/bella/pipeline/l1/eval1.py#L1206-L1226), [`pipeline/l1/frontend.py:832-890`](file:///home/nathan/workspaces/nth/bella/pipeline/l1/frontend.py#L832-L890), [`pipeline/l1/wf.py:105-117, 199, 201, 211`](file:///home/nathan/workspaces/nth/bella/pipeline/l1/wf.py#L105-L117), [`pipeline/l1/modules.py:84-94`](file:///home/nathan/workspaces/nth/bella/pipeline/l1/modules.py#L84-L94), and [`pipeline/l1/run.py:99-101`](file:///home/nathan/workspaces/nth/bella/pipeline/l1/run.py#L99-L101)
- **Problem:**
  1. **Keyword sub-dict evaluation order after `**kwargs` (`f(**{"a": 0}, a=s1(), b=s2())`):** In CPython 3.15.2 (`Python/codegen.c:subkwargs`), a contiguous run of explicit `k=v` keywords (up to 15 pairs) following a `**mapping` unpack is evaluated completely into a sub-dict (`BUILD_MAP`) and then merged via `DICT_MERGE` (the same mechanism `eval1.py:1129-1167` implements for `dict_display`). `Interpreter.arguments` ([`eval1.py:1206-1212`](file:///home/nathan/workspaces/nth/bella/pipeline/l1/eval1.py#L1206-L1212)) checks `if name in kwargs:` immediately after each keyword, aborting after `s1()` before `s2()` is evaluated.
  2. **Missing `SyntaxError`s in `_Imports` (`lazy import` in `try` and `from m import *` in `class`):**
     - `_Imports.mode` ([`frontend.py:833-836`](file:///home/nathan/workspaces/nth/bella/pipeline/l1/frontend.py#L833-L836)) checks `if self.scope != "module":` when `lazy=True`, but forgets `if self.guarded: raise SyntaxError(f"lazy import not allowed inside try/except blocks (line {line})")`.
     - `_Imports.import_from` ([`frontend.py:888-889`](file:///home/nathan/workspaces/nth/bella/pipeline/l1/frontend.py#L888-L889)) checks `if star and self.scope == "function":` instead of `if star and self.scope != "module":`, allowing `class C: from math import *` (which is a `SyntaxError` in Python 3).
  3. **`nonlocal`/`global` validation and `_writes_globals` over-relaxation in `wf.py` and `eval1.py`:**
     - `Interpreter.load` ([`eval1.py:518-572`](file:///home/nathan/workspaces/nth/bella/pipeline/l1/eval1.py#L518-L572)) never checks `if name in scope.nonlocals_:` for a function scope, so `x = "global"; def f(): nonlocal x; return x` compiles and returns `"global"` instead of raising `SyntaxError: no binding for nonlocal 'x' found`. Likewise, `declarations` ([`frontend.py:508-522`](file:///home/nathan/workspaces/nth/bella/pipeline/l1/frontend.py#L508-L522)) does not reject `def f(x): global x` (`SyntaxError: name 'x' is parameter and global`) or `global x; nonlocal x`.
     - In [`wf.py:105-117, 199`](file:///home/nathan/workspaces/nth/bella/pipeline/l1/wf.py#L105-L117), `_writes_globals(m)` (added in `e95e61f` before `58bb34b` introduced `strict=False` for library modules under P-3) sets `scope.star = True` on *every* module—including `strict=True` user program modules—whenever `globals()` appears anywhere in the module, even in a read-only call (`_ = globals()`). This disables compile-time `NameError` checking across the entire user module, contradicting spec v0.12 §8 (*"The program's own modules keep the compile-time NameError"*). Furthermore, `_declared_global` ([`wf.py:136-160, 201`](file:///home/nathan/workspaces/nth/bella/pipeline/l1/wf.py#L136-L160)) adds any `global x` declaration to `module.bound` even if `x` is never assigned anywhere in the module or its functions.
  4. **`ModuleSystem` (`--modules closure`) omits `"program"` modules from `self.closure` and blocks D-20 modules after `STARTUP_ROOTS`:**
     - In [`pipeline/l1/modules.py:86-93`](file:///home/nathan/workspaces/nth/bella/pipeline/l1/modules.py#L86-L93), `ModuleSystem.__init__` populates `self.closure` for `m["status"] == "compiled"` and `"shim"`, but omits `m["status"] == "program"` (unlike `tools/scope.py:455`). Consequently, `system.prelower()` never pre-lowers the target's vendored/program modules in the lock (`itsdangerous.*` in `service_easy_tokens`, `humanize.*` in `data_easy_sales`), lowering them lazily at runtime during `import` instead of ahead of time per P-1.
     - In [`pipeline/l1/run.py:99-101`](file:///home/nathan/workspaces/nth/bella/pipeline/l1/run.py#L99-L101), `system.activate(STARTUP)` (which imports `STARTUP_ROOTS`) runs *before* `for name in blocked: sys.modules[name] = None`.
- **Reproduction:**
  ```python
  # 1. Keyword sub-dict evaluation order after **kwargs
  events = []
  def s1(): events.append("s1"); return 1
  def s2(): events.append("s2"); return 2
  def f(**kw): pass
  try:
      f(**{"a": 0}, a=s1(), b=s2())
  except TypeError:
      print(events)
  # CPython 3.15.2: ['s1', 's2']
  # eval1:          ['s1']

  # 2. lazy import in try & import * in class
  # try: lazy import math\nexcept: pass  -> CPython: SyntaxError; eval1: OK
  # class C: from math import *          -> CPython: SyntaxError; eval1: OK

  # 3. nonlocal reading global & read-only globals() disabling wf1
  x = "global_val"
  def g():
      nonlocal x
      return x
  # CPython 3.15.2: SyntaxError: no binding for nonlocal 'x' found
  # eval1:          returns 'global_val'
  ```
- **Recommendation:**
  - Group contiguous explicit `k=v` runs in `Interpreter.arguments` (`eval1.py:1206-1226`) using the same sub-dict batching as `dict_display`, or evaluate all `v` in a run before checking duplicate keys.
  - In `_Imports.mode` ([`frontend.py:834`](file:///home/nathan/workspaces/nth/bella/pipeline/l1/frontend.py#L834)), raise `SyntaxError` when `lazy and self.guarded`; in `_Imports.import_from` ([`frontend.py:888`](file:///home/nathan/workspaces/nth/bella/pipeline/l1/frontend.py#L888)), change `self.scope == "function"` to `self.scope != "module"`.
  - Validate `nonlocal` bindings and parameter/`global`/`nonlocal` conflicts at compile time in `wf.py` (and check `if name in scope.nonlocals_:` in `Interpreter.load`); remove `_writes_globals(m)` from `strict=True` user modules in `wf.py:199` (since P-3's `strict=False` already covers library modules); and only count `global x` in `_declared_global` when the declaring scope actually assigns or deletes `x`.
  - Include `m["status"] == "program"` in `ModuleSystem.closure` ([`modules.py:90-93`](file:///home/nathan/workspaces/nth/bella/pipeline/l1/modules.py#L90-L93)) (distinguishing the entry script from vendored packages for `strict`), and set `sys.modules[name] = None` for `blocked` before importing `STARTUP_ROOTS` in [`run.py:99-101`](file:///home/nathan/workspaces/nth/bella/pipeline/l1/run.py#L99-L101).
