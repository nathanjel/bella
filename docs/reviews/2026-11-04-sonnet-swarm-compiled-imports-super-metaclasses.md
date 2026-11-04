# Bella Review (`e827a47..62d083b`): swarm of Sonnet reviewers
- **Date:** 2026-11-04
- **Reviewer:** eight `claude-sonnet-5-5` agents, one per focus area, each independent of the others and of G10 (they did not see it)
- **Commit range reviewed:** `e827a47..62d083b`
- **Reference interpreter:** CPython 3.15.2 (`.venv/bin/python`), source read from the 3.15.2 tarball

Requested by the author in place of astra-low, whose run failed. The reports below are as the agents returned them. Scratch paths in them no longer exist.

## C half of imports, sys.exit, exit clearing (focus `imports`)

#### `__del__` at exit sees the program's own globals already set to None
Severity: high (a wrong answer on a common pattern; output is lost and stderr gets a spurious "Exception ignored")
Where: runtime/src/call.cpp:1518-1543 (`clear_module`, `clear_modules`)
Repro (h1.py):
```python
import sys
LABEL = "res"
def helper(): return "helper"
class D:
    def __del__(self): print("del", LABEL, helper(), sys.version_info[0])
d = D()
```
CPython: stdout `del res helper 3`, exit 0 / Bella: stdout empty, stderr "Exception ignored while calling deallocator ... TypeError: 'NoneType' object is not callable", exit 0
Also seen: `sys.exit(9)` in `__del__` gives `AttributeError: 'NoneType' object has no attribute 'exit'`, and `sys.stderr.write` in `__del__` fails the same way. `print(__name__)` in `__del__` prints None, and `len(globals())` differs.
Why: `clear_module` rebinds each global to None in insertion order, running finalisers as it goes. In CPython a module whose classes define `__del__` is always in a dict-class-function-dict cycle, so the GC runs the finalisers with the namespace intact. Names defined before the object are the ones lost. D-07 makes the order unspecified; it does not cover finalisers seeing None.

#### `from pkg import *` does not import the submodules listed in `pkg.__all__`
Severity: high (silent wrong answer on ordinary code)
Where: pipeline/closed_world.py:103 (`_imports` drops `*`; `scan` only follows named fromlist entries)
Repro: pkgstar/__init__.py is `__all__ = ["sub", "mod1"]`; pkgstar/sub/__init__.py and pkgstar/mod1.py print a line each. main.py:
```python
from pkgstar import *
print(mod1)
```
CPython: prints "sub init", "mod1", then the module repr, exit 0 / Bella: `AttributeError: module 'pkgstar' has no attribute 'sub'`, exit 1. `__import__("pkgstar", fromlist=["*"])` silently leaves sys.modules as ['pkgstar'].
Why: the build never registers `pkgstar.sub` or `pkgstar.mod1`. `_handle_fromlist` then swallows the ModuleNotFoundError, as CPython does for absent modules.

#### `sys.exit(obj)` whose `__str__` raises aborts the process
Severity: medium
Where: runtime/src/call.cpp:1546 (`exit_status`, called from the catch block in `run_main` around line 1653)
Repro (f7.py):
```python
import sys
class X:
    def __str__(self): raise ValueError("no str")
sys.exit(X())
```
CPython: exit 1, blank stderr / Bella: "terminate called after throwing an instance of 'bella::PyError'", exit 134 (core dump)
Why: `str_of` throws inside a catch handler, and nothing around `exit_status` catches it. CPython's handle_system_exit clears the error and exits 1.

#### `SystemExit.code` is ignored or refused; `args` is used instead
Severity: medium
Where: runtime/src/call.cpp:1546-1560
Repro A (f2.py): `class E(SystemExit): code = 13` with `def __init__(self): pass`, then `raise E()`. CPython exit 13 / Bella exit 0.
Repro B: `e = SystemExit(3); e.args = (11,); raise e`. CPython exit 3 / Bella exit 11.
Repro C: `e = SystemExit(3); e.code = 9; raise e`, or reading `e.code` in `except SystemExit as e:`. CPython exit 9 / Bella `bella: not implemented: SystemExit.code`, exit 70. That is a clean refusal, but reading `e.code` is a common idiom.

#### Closed world cannot see a package's `__path__` being extended, or a module `__getattr__` returning for `__path__`
Severity: low (the wrong exception, not a refusal)
Where: runtime/src/imports.cpp (`i_bella_find`); pipeline/closed_world.py
Repro 1: pp/__init__.py is `__path__.append(".../elsewhere")`, with elsewhere/extra.py present. main.py does `import pp.extra`. CPython prints "pp.extra from elsewhere" / Bella `ModuleNotFoundError: No module named 'pp.extra'`.
Repro 2: any.py is `def __getattr__(n): return 7`, and main does `import any.sub`. CPython `TypeError: 'int' object is not iterable` / Bella ModuleNotFoundError.

#### Relative import from `__main__` after assigning `__package__`
Severity: low
Where: pipeline/closed_world.py `_package_of("__main__")`
Repro: main.py is `__package__ = "pk2"` then `from . import mod`, with pk2/mod.py present. CPython imports it / Bella `ModuleNotFoundError: No module named 'pk2'`.

#### `import *` with a bad `__all__` has the wrong message or exception (it uses generic subscripting, not PySequence_GetItem)
Severity: low
Where: runtime/src/imports.cpp:491-530 (`import_star`)
Repro: `__all__ = 5`, `None`, `{"a"}`, or an instance with only `__iter__`. CPython `TypeError: 'int' object does not support indexing` / Bella "is not subscriptable".
Also `__all__ = {"a": 0}`: CPython `TypeError: dict is not a sequence` / Bella `KeyError: 0`.
Also `__all__ = range(3)`: CPython `TypeError: Item in m.__all__ must be str, not int` / Bella `'range' object is not subscriptable`. This one is really a gap in `range` indexing: `range(3)[0]` fails the same way outside imports.

#### `__import__("pkg.sub.")` and `__import__("pkg..sub")` succeed
Severity: low
Where: pipeline/closed_world.py `find` (an empty `tail` matches the parent's `__init__.py`)
Repro: `__import__("pkg..sub")` or `__import__("pkg.sub.")` with a real package pkg. CPython `ModuleNotFoundError: No module named 'pkg.'` (or 'pkg.sub.') / Bella returns pkg. The build registers module "pkg." as pkg/__init__.py, so it would run twice.

#### Module read-only attributes are accepted silently, and `module()` argument errors differ
Severity: low
Repro 1: `m = types.ModuleType("x"); m.__dict__ = {}`. CPython `AttributeError: readonly attribute` / Bella accepts it. The same happens for `m.__class__ = 5`; CPython raises `TypeError: __class__ must be set to a class, not 'int' object`.
Repro 2: `del m.__dict__` gives a different AttributeError text.
Repro 3: `ModuleType("a", name="b")` and `ModuleType(nme="n")` give "unexpected keyword argument" in Bella. CPython says "argument for module() given by name ('name') and position (1)" and "missing required argument 'name' (pos 1)".
Repro 4: `ModuleType.__doc__` is None in Bella.

#### Exit-time clearing order differs after an uncaught exception
Severity: low (D-07 calls the order unspecified, but CPython's order is deterministic)
Repro (t6/main2.py): main imports mb and ma, and holds objects with `__del__`. It then raises ValueError. CPython finalises mb and ma's objects before main's. Bella finalises main's first. The cause is that sys.last_exc keeps main's frame alive in CPython.
A similar order difference appears when `keep = e` holds an exception whose traceback has a frame with a `__del__` local.

Suspected, not reproduced:
- `__package__ != __spec__.parent` is refused (NotImplemented) where CPython only emits a DeprecationWarning, which has no effect on stdout or exit status.
- Float `sys.exit(1.5)` and `sys.exit(2**64)` are refused (float constants and BigInt, known gaps).

Checked and clean (output identical to CPython, apart from the findings above):
- Packages, relative imports at levels 1 to 3, and `import a.b.c as x`. Circular imports, including the partially-initialised messages and a module whose `__file__` shadows a stdlib name.
- A module failing partway, then re-imported. `__main__` imported from a module.
- `__import__` with about 60 argument combinations, including its TypeError, ValueError and OverflowError texts.
- ImportError, ModuleNotFoundError and name_from fields. Module `__getattr__`, `__dir__` and repr. `import *` with and without `__all__`.
- `sys.exit` with 35 values and exit statuses. `__del__` raising during exit, and `finally` interacting with `SystemExit`.
- Uncaught exception tracebacks (frames match; source lines and carets are absent, a known gap I did not report).
- Scratch files: .../scratchpad/rev/imports/t1 through t18.

## bootstrap.py and module presentation (focus `bootstrap`)

#### `from pkg import *` does not import the submodules named in `pkg.__all__` unless something else names them
Severity: medium (wrong answer, not a refusal)
Where: pipeline/closed_world.py:101 (`a.name != "*"` drops the star from the fromlist, so `scan` never calls `find(f"{target}.{x}")` for `__all__` entries). Runtime `_handle_fromlist` is then correct but the module isn't in the registry.
Repro: `pk/__init__.py` = `__all__ = ['sub']`; `pk/sub.py` = `v = 1`; `main.py` = `from pk import *` / `print(sub.v)`
CPython: prints `1`, exit 0 / Bella: `AttributeError: module 'pk' has no attribute 'sub'`, exit 1
Why: CPython's `_handle_fromlist` imports `pk.sub` for `*`. The same failure shows with `__import__('pk', fromlist=['*'])`: sys.modules has only `pk`. The build has to read `__all__` (or take every module of the package) for `import *`.

#### Module `__class__` and `__dict__` assignment is accepted silently and writes into the namespace
Severity: low-medium
Where: module setattr in runtime (imports.cpp area)
Repro: `import m` (any module), then `m.__class__ = int` and `m.__dict__ = {'a': 1}` in try/except, then `print(list(vars(m)))`
CPython: TypeError ('__class__ assignment only supported for mutable types or ModuleType subclasses') and AttributeError ('readonly attribute'); vars unchanged
Bella: no error; `vars(m)` ends with `'__class__', '__dict__'` as ordinary entries (type and `__dict__` are unchanged).

#### Relative-import ImportErrors raised by the runtime have `.msg == None`
Severity: low
Where: runtime/src/imports.cpp:146,152,156 (`raise_new("ImportError", ...)`, which skips ImportError's init)
Repro: `try: from . import x` / `except ImportError as e: print(e.msg)`. Same with `__import__("x", {'__package__': 'a'}, None, [], 2)`.
CPython: prints the message, e.g. `attempted relative import with no known parent package` / Bella: `None`. `args` and `str` are right. Lines 427, 432, 496 and 692 use the same path.

#### `sys.__doc__`, `builtins.__doc__` and `types.ModuleType.__doc__` are wrong
Severity: low
Repro: `import sys, builtins; print((sys.__doc__ or '')[:20], type(sys).__doc__ is None, '__doc__' in vars(sys))`
CPython: `This module provides ` / False / True / Bella: `The base class of th` (object's doc, because the module dict has no `__doc__`) / True / False.
Also `list(vars(sys))` and `list(vars(builtins))` start differently: CPython `__name__, __doc__, __package__, __loader__, __spec__, addaudithook...` / `__build_class__, __import__, abs...`; Bella has no `__doc__` and a different order. `vars(__main__)`, plain modules, packages, submodules and `_types` matched CPython exactly.

#### `types.SimpleNamespace` differs in name, `__dict__` and a few messages
Severity: low
Repro (each line separately):
- `types.SimpleNamespace().q`: CPython `'types.SimpleNamespace' object has no attribute 'q'`; Bella `'SimpleNamespace' ...`. The same prefix differs in `hash(ns)` and `ns < ns`.
- `ns.__dict__ = {}`: CPython AttributeError('readonly attribute'); Bella allows it.
- `NS({}, {})`: CPython `SimpleNamespace expected at most 1 argument, got 2`; Bella `SimpleNamespace.__init__() takes from 1 to 2 positional arguments but 3 were given`. `__replace__(5)` and `NS.__repr__(5)` / `NS.__init__(object())` also differ (Bella AttributeError or other text where CPython raises "descriptor ... requires").
Repr, eq, kwargs, positional mapping, subclasses, recursive repr and `__replace__` matched CPython.

#### SourceFileLoader class shape
Severity: low
Where: runtime/prelude/bootstrap.py:599
Repro: `L = m.__spec__.loader; print(type(L).__bases__, hasattr(L,'load_module'), L.get_filename.__qualname__, type(L).__init__.__module__)`
CPython: `(FileLoader, SourceLoader)`, False, `FileLoader.get_filename`, `_frozen_importlib_external` / Bella: `(object,)`, True (an unmarked refusing `load_module`), `SourceFileLoader.get_filename`, `_frozen_importlib`. `set_data`, `path_mtime` and `_cache_bytecode` are absent. Classes defined in the prelude also lack `__weakref__` in their `vars` (BuiltinImporter, ModuleSpec).

#### `__package__` != `__spec__.parent` is refused even where CPython's DeprecationWarning is ignored
Severity: low (clean refusal on in-scope behaviour)
Where: runtime/src/imports.cpp:133
Repro: in `pk/chg.py`: `__package__ = 'other'` then `from . import sib`
CPython: imports `other.sib`, no output (the warning is ignored outside `__main__`) / Bella: `bella: not implemented: the DeprecationWarning ...`, exit 70.

Suspected, not reproduced:
- `FrozenImporter` lacks `find_spec`, `get_code` and `get_source` (the `_requires_frozen` ones), and `_fix_up_module` is gone, none marked `bella:`. The frozen path can't run compiled (stat/abc need `_stat` or `_abc`), so unreachable today.
- CPython's `BuiltinImporter.create_module(sys.__spec__)` resets `sys.__spec__` to None (repr `<module 'sys'>`). Bella returns the module untouched. Esoteric.
- `import __hello__` (frozen-only in CPython) gives ModuleNotFoundError in Bella.
- Traceback lines differ in stderr (no source text), and `tb_next` is not implemented.

Checked and clean:
- A line-by-line diff of bootstrap.py against CPython's `_bootstrap.py` and `_bootstrap_external.py`: all `ModuleSpec` logic, `_init_module_attrs`, `_load_unlocked`, `_find_and_load*`, `_handle_fromlist`, `cache_from_source`/`_get_cached` and `get_filename`/`is_package`/`exec_module` are faithful.
- Full `__spec__` attribute dumps for `__main__`, a plain module, a package, a submodule, `sys`, `builtins`, `_types` and stdlib `types` (name, origin, parent, has_location, cached, loader_state, vars order, repr), plus `__loader__`, `__package__`, `__file__`, `__path__`, `__builtins__`, `globals()` order (docstring, annotations) and module repr in every spec/loader state.
- `_initializing` (body, parent `_uninitialized_submodules`), retries after a body raised (module, package, SystemExit), circular imports and their messages, `__package__`/`__spec__` mutation, `__name__` rewrite, loader `exec_module` re-run and into a fresh module, local modules shadowing `types`/`_types`, `ImportError` attribute sets, `__getattr__`/`__dir__` module hooks and non-ASCII names.
- Not run: `os`/`stat`/`abc` (blocked by missing native modules), `dir()` on objects, `sys.implementation` (all known gaps).

## lazy imports (PEP 810) (focus `lazy`)

I found no wrong answer, crash or hang in lazy-import semantics for 23fb0ba. The defects below are only wrong error-message text and missing docstrings, plus two refusals where CPython 3.15.2 succeeds. I ran about 45 hand-written programs plus roughly 150 randomly generated ones and compared stdout, stderr (source-excerpt and caret lines stripped) and exit status. Programs are in /tmp/claude-1001/-home-nathan-workspaces-nth-bella/3c0181b5-e55a-4b93-8a5d-84682fffa693/scratchpad/rev/lazy/t*/ and fz/.

#### `__lazy_import__` called with a different globals dict at module level is refused
Severity: low
Where: runtime/src/imports.cpp:800
Repro (module level, `modx.py` beside it):
```
if False:
    import modx
g = dict(globals())
z = __lazy_import__("modx", g)
print(type(globals()["z"]).__name__)
```
CPython: prints `lazy_import`, exit 0. Bella: `bella: not implemented: the SyntaxError "'lazy import' is only allowed at module level"`, exit 70.
Why: CPython's check (`_PyImport_LazyImportModuleLevelObject`, Python/import.c) is only `frame->f_globals != frame->f_locals`, a property of the calling frame. Bella also requires `globals == frame->module->dict`, which is an extra condition.

#### `__lazy_import__` called from a function or class body is refused, not raised as SyntaxError
Severity: low
Where: runtime/src/imports.cpp:801
Repro:
```
def f():
    try: __lazy_import__("modx")
    except SyntaxError as e: print("SyntaxError", e)
f()
```
CPython: prints `SyntaxError 'lazy import' is only allowed at module level`, exit 0. Bella: `not implemented ... (SyntaxError: step 3b)`, exit 70.
Why: this is a known TODO. A program that catches the SyntaxError can't continue. The same applies to `tr(__lazy_import__, ...)` through any helper function.

#### `lazy_import.resolve(1)` gives the wrong TypeError text
Severity: low
Where: runtime/src/imports.cpp:978-980 (`lazy_resolve_m` uses `positional_only`)
Repro: `lazy import modx` in `main.py`, with `modx.py` beside it:
```
H = [globals()["modx"]]
try: H[0].resolve(1)
except TypeError as e: print(e)
```
CPython: `lazy_import.resolve() takes no arguments (1 given)`. Bella: `resolve() takes 0 positional arguments but 1 were given`.
Why: CPython defines `resolve` as METH_NOARGS, so it uses the no-argument message.

#### `lazy_import` has no docstrings, and `lz.resolve.__doc__` is `object`'s
Severity: low
Where: runtime/src/imports.cpp:1206-1209 (`init_imports`)
Repro: with the same `H` as above, run `print(type(H[0]).__doc__, H[0].resolve.__doc__, H[0].__doc__)`.
CPython: `Represents a lazy import that will be resolved on first use. ...`, then `Resolve the lazy import and return the imported object.`, then the class docstring. Bella: `None`, then `The base class of the class hierarchy.`, then that same `object` docstring.
Also `list(type(lz).__dict__)`: CPython gives `['__repr__','__getattribute__','resolve','__doc__']`, Bella gives `['__new__','__repr__','resolve']`.
Why: no `__doc__` is set on the type or on `resolve`, and the `__doc__` lookup falls through to `object`.

#### Assigning over a method-descriptor name gives the wrong message (generic, not lazy-specific)
Severity: low
Where: generic `setattr`; surfaced via `setattr(lz, "resolve", 1)`
Repro: `[].append = 1` and `(1).real = 1`
CPython: `'list' object attribute 'append' is read-only` and `attribute 'real' of 'int' objects is not writable`. Bella: `'list' object has no attribute 'append' and no __dict__ for setting new attributes`, and the same shape for `int`. The `lazy_import` case behaves the same way.

Suspected, not reproduced:
- `sys.lazy_modules` is absent, so reading it is a clean refusal (known; `lazy_modules_add` and `_PyImport_DiscardLazyModule` are skipped).
- Uncaught exceptions that carry `__notes__` stop with a clean refusal. This is the path `lazy_add_exception_cause` takes when the error already has a chain.
- `class Sub(type(lz))` is refused (`subclassing the built-in type`), where CPython raises a TypeError.
- `del lz.resolve` and `object.__getattribute__` are refused.

Checked and clean (stdout, stderr and exit status identical to CPython):
- **Declaration forms:**
  - `lazy import a`, `a.b.c`, `a.b as x`, `lazy from a import b [as c]`.
  - Multi-line and backslash declarations: the cause traceback line, and the `__notes__` declaration line.
  - Relative lazy imports inside packages, and lazy imports of the builtin modules `sys` and `builtins`.
- **First use and reification:**
  - first use in a function, a class body, a default argument, a decorator, a base class, a metaclass, an f-string, `+=` and a `global` assignment;
  - `del` of a lazy name and rebinding before first use;
  - another module's name replacing the lazy name during load;
  - `globals()` and `.get/.copy/dict()` leaving placeholders in place;
  - `dir(module)`, `vars`, `hasattr`, `getattr` with a default, `from m import name`, and star-import with and without `__all__`.
- **Error and retry paths:** a load that raises then succeeds on retry; missing module and missing name; the cause versus `__notes__` paths (original `__context__`, `__cause__` and `from None`); a failing nested lazy; `SystemExit` raised by a lazy module.
- **Cycles:** `ImportCycleError` (direct, via `hasattr`/`getattr`, and uncaught); a self-referential lazy import.
- **Pending submodules:**
  - a parent attribute triggering a pending submodule, including missing and failing children;
  - a non-package parent, a shadowing `b` attribute, a package with `__getattr__`;
  - package `__init__` files that use lazy imports and cross-import.
- **`__lazy_modules__`:** list, tuple, frozenset, string, a value of the wrong type, `del`, and use inside `try` or a function.
- **`__lazy_import__`:** direct calls at module level with argument and keyword errors, `fromlist` forms, level, and bad globals.
- **Module-level `__getattr__` and `__dir__`** bound as lazy names.
- **The lazy object itself:** repr, name, `type`, `resolve()`, and the errors from calling, indexing, constructing or `len()` of one.
- **Syntax rejections:** try/function/class/star are clean refusals with exit 70, where CPython gives a SyntaxError with exit 1.
- **Random differential programs:** about 150 generated programs mixing lazy and eager `import`/`from` over a small package tree, each with probes and sys.modules snapshots. None differed.

I did not exercise: the standard library under `lazy import`, the filter and mode APIs (`sys.set_lazy_imports*`), threads, or custom `__import__` hooks (excluded by E-04/E-06).

## closure discovery and build caches (focus `closure`)

#### `from pkg import *` and `__import__(..., fromlist=/level=)` miss submodules the import loads
Severity: high (wrong answer on a normal package idiom)
Where: pipeline/closed_world.py:103 (`if a.name != "*"`), :104-110 (only args[0] is read)
Repro (pkg/__init__.py is `__all__ = ["sub"]`, pkg/sub.py is `print("sub loaded"); X = 1`):
```python
from pkg import *
print(sub.X)
```
CPython: `sub loaded` then `1`, exit 0. Bella: `AttributeError: module 'pkg' has no attribute 'sub'`, exit 1.
Same cause, three more cases (all run):
- `m = __import__("pkg", fromlist=["a"]); print(m.a.__name__)` gives `AttributeError ... 'a'`. CPython prints `pkg.a`.
- Inside pkg/__init__.py, `__import__("sub", globals(), None, ["x"], 1)` gives `ModuleNotFoundError: No module named 'pkg.sub'`. CPython imports `pkg.sub`. The `level` argument is ignored and the name is treated as absolute.
- `import builtins; builtins.__import__("d")` gives `ModuleNotFoundError`. CPython imports d. Only a bare `__import__` name is recognised.
Why: `_handle_fromlist` imports each name in `__all__` and each fromlist name as a submodule. Discovery never sees them, so the registry lacks the module.
Not demonstrable, because `importlib` itself is refused by name: `import importlib as il; il.import_module("c")` and `from importlib import import_module` are not recognised (line 109 needs the literal name `importlib`). `import_module(".b", "pkg")` with a relative name is not resolved either.

#### A directory without `__init__.py` shadows a standard-library module and the program is refused
Severity: medium
Where: pipeline/closed_world.py:141-142
Repro: a directory `types/` (any file inside, no `__init__.py`) next to main.py, which holds `import types; print(types.SimpleNamespace(a=1))`.
CPython: `namespace(a=1)`, exit 0. Bella: `bella: not implemented: importing 'types', a namespace package (step 3b)`, exit 70.
Why: a namespace package is only used if no regular module or package of that name exists on any later `sys.path` entry. A stdlib module wins, but Bella decides at the first entry. Any data or log directory named `logging`, `test`, `json` or `email` triggers it.

#### A non-UTF-8 source encoding crashes the build; a BOM is refused
Severity: medium
Where: pipeline/closed_world.py:157, pipeline/build.py:181,191 (`read_text(encoding="utf-8")`)
Repro: lat.py is `# -*- coding: latin-1 -*-` plus `print("caf\xe9")` (byte 0xe9); main.py is `import lat`.
CPython prints `café`, exit 0. Bella: a Python traceback from `UnicodeDecodeError` inside `scan`, exit 1 (not the refusal exit 70).
A UTF-8 BOM, in a module or in the main file, gives `bella: refused: invalid non-printable character U+FEFF`, exit 70. CPython runs it.
Why: PEP 263 cookies and the BOM are not honoured when the source is read.

#### Relative program path gives a relative `File` name in tracebacks
Severity: medium
Where: pipeline/build.py:238 (`build(program, argv[0])`) and :181
Repro: in the program's directory, r.py is `raise KeyError(1)`. Run `python r.py` and `build.py --run r.py`.
CPython: `File "/abs/path/r.py", line 3` (3.15 makes the main script's co_filename absolute). Bella: `File "r.py", line 3`.
Why: the filename is passed through as typed, while module units use resolved absolute paths. `__file__` is absolute in both.

#### `BELLA_KEEP_DEBUG` is not in the link key
Severity: low
Where: pipeline/build.py:195-203
Repro: build p.py, then build it again with `BELLA_KEEP_DEBUG=1`. Both builds print the same path, the same 2152760 bytes, and `readelf -S` shows 0 debug sections. The second build returns the stripped binary, and the reverse order has the same problem.

#### Pipeline cache key is empty when the checkout path contains a directory named `tests`
Severity: low-medium
Where: pipeline/build.py:86 (`"tests" not in f.parts` tests the absolute path)
Repro: I copied pipeline/ and runtime/include/ to `.../tests/bella` and to `.../ok/bella`.
- `_pipeline_bytes()` has 0 files in the first copy and 44 in the second.
- After editing `emit_module` in each copy, `lowered_unit("x = 1\n", ...)` returns the old text in the first copy and the new text in the second.
Effect: compiler edits never invalidate `lowered_unit` or `runtime_library` there, so stale objects get linked.

#### Lowered-unit cache ignores `CXX`, `CXXSTD` and the system headers
Severity: low
Where: pipeline/build.py:63, pipeline/backend/cpp.py:55-62 (`header_macros()` is compiler-dependent)
Repro: `lowered_unit("def f():\n    unix = 1\n    return unix\n", ...)` under default `-std=c++26`, then `CXXSTD=gnu++26`.
- The second call reuses the text with a bare `Ref unix;`. Under gnu++26 `unix` is a macro, so the unit fails with `no matching function for call to FrameGuard(..., int)`.
- A fresh cache under `CXXSTD=gnu++26` escapes the name and compiles.
A glibc update that adds a macro does the same.

#### `_forget_previous` deletes another spelling's binary
Severity: low
Where: pipeline/build.py:216-220
Repro: from dbg/, `build.py p.py` prints A, then `build.py /abs/dbg/p.py` prints B. A's directory is gone and only B exists. The pointer is keyed by the resolved path, but the output key depends on `argv[0]`, `CXX` and `CXXSTD`. A concurrent build of the same program under another spelling can also delete a binary just before `execv`. I did not reproduce that race in 6 alternating iterations.

#### Wrong module picked: a local package named `importlib`
Severity: low
Where: pipeline/closed_world.py:132-142 (FIRST is checked only for top-level names)
Repro: a local `importlib/__init__.py` plus `importlib/util.py` printing LOCAL, and `import importlib.util`.
CPython uses the frozen `importlib.util` (`<frozen importlib.util>`). Bella loads the local util.py.
Why: FrozenImporter matches the dotted name `importlib.util` whatever the parent's path.

#### `__file__` of a symlinked entry program is the symlink target
Severity: low
Where: pipeline/build.py:192 (`program.resolve()`)
Repro: link/main.py is a symlink to real/main.py, and `print(__file__)`.
CPython prints `.../link/main.py`. Bella prints `.../real/main.py`.
`sys.path[0]` is the real directory in both.

#### A reachable module with a SyntaxError refuses the whole build
Severity: low
Where: pipeline/closed_world.py:157
Repro: `try: import broken_syntax / except SyntaxError: print("caught")` with `def (` in broken_syntax.py. CPython prints `caught`. Bella: `refused: invalid syntax`, exit 70.

Suspected, not reproduced:
- A concurrent `rmtree` in `_forget_previous` while another process links into the same output directory.
- The compiler binary version is not in the `_object` key.

Checked and clean:
- Discovery: the order of an entry program's directory against built-in and frozen names; package vs module; non-ASCII, underscore and digit module names (`namespace_of` is injective, and the prefix avoids C++ keywords); relative imports to level 3; lazy imports (`lazy from pkg import sub`); an entry program named after a stdlib module that imports itself; `try:` imports of missing modules; an entry program outside the current directory.
- Caches: a module changing, or the module set changing, with main unchanged; two copies of one source at two paths; `runtime_library` and `_object` inputs, including the .inc files and the prelude; parallel `_object` and `lowered_unit` writes.
- Not tested: `closure.lock.json` and `manifest.toml` edits (reasoned only: they reach the build through the main unit's text).

## lowering and backend changes (focus `lowering`)

#### A try whose body cannot fall through, followed by `else:`, fails wf2 and the build aborts
Severity: medium (valid, ordinary code; exits 1 with a Python traceback, not the exit-70 refusal). Pre-existing: the same failure occurs at e827a47. `_falls_through`'s Try case, which is in the focus range, has the same blind spot.
Where: pipeline/l2/lower.py:234-246 (`L.Try` keeps `orelse` after a body that never completes) and `_falls_through` Try case at lower.py:556; pipeline/l2/wf.py:261 (`block(*body, *orelse)`).
Repro:
```python
def g() -> int:
    return 1

def f() -> int:
    try:
        return g()
    except ValueError:
        print("v")
    else:
        print("else")
    return 0

print(f())
```
CPython: prints `1`, exit 0. Bella: `WellFormednessError: f: unreachable statement Line`, exit 1.
Why: `block()` drops statements after a terminator, but a Try's `orelse` after a body ending in `return`, `raise`, `break` or `continue` is never dropped, so wf2 rejects it. `try: raise E / except E: ... / else: ...` followed by any statement fails the same way, and so does `try: continue / except: / else:` inside a loop.

#### A local, parameter or global-in-function named `match` breaks C++ compilation when used inside an `except` body
Severity: high (`match` is a common name, for example a `re.match` result)
Where: pipeline/backend/cpp.py:520-524. The emitter declares `bool match = ...` and `if (match) {`, and `match` is neither in `_KEYWORDS` nor matched by `_COMPILER_NAME`.
Repro:
```python
def f() -> int:
    match = 5
    try:
        raise ValueError()
    except ValueError:
        print(match)
    return match
print(f())
```
CPython: `5` and `5`, exit 0. Bella: g++ error `invalid initialization of reference of type 'const bella::Ref&' from expression of type 'bool'` at `rt::load_fast(match, "match")`, exit 1.
Why: the handler body sits inside the block where the emitter's own `bool match` shadows the Python local. Every other emitter-made name goes through `aux()`, which is checked against `_COMPILER_NAME`. Rename it with `aux("m")`, or add `match` to the reserved names.

#### `contract_assert`, a C++26 keyword, is not escaped by cpp_name
Severity: low to medium (valid Python identifier, rare)
Where: pipeline/backend/cpp.py:33-40 (`_KEYWORDS`)
Repro:
```python
def f(contract_assert: int) -> int:
    return contract_assert + 1
print(f(1))
```
CPython: `2`. Bella: g++ `expected primary-expression before 'contract_assert'` (also `Ref contract_assert;`), exit 1.
Why: `_KEYWORDS` lacks the C++26 keyword. I probed about 200 other C++ keywords and common identifiers by compiling them as `Ref X;`, and only this one failed. That probe covered `reflexpr`, `synchronized`, `atomic_*`, `typeof`, `pre`, `post`, `linux` and `unix`.

#### The line of a `while` test, or of a `for` iterator's `__next__`, is wrong from the second iteration on
Severity: low to medium (stderr traceback lines; `tb_lineno` is not implemented yet)
Where: pipeline/l2/lower.py:200-217. `stmt()` emits `Line` before `capture()`, so the `Line` is outside the `Loop` body, and the test and `ForNext` run again with `frame.line` left at the last body statement.
Repro, exception from the iterator on the second pass:
```python
class It:
    def __init__(self) -> None:
        self.n = 0
    def __iter__(self) -> "It":
        return self
    def __next__(self) -> int:
        self.n += 1
        if self.n == 3:
            raise KeyError("it")
        return self.n

def f() -> int:
    t = 0
    for x in It():
        t += x
        t += 1
    return t

f()
```
CPython: the traceback entry for `f` says `line 17` (the `for`). Bella: `line 19`.
The same happens when `while g(i):` raises on the second or later test (CPython says the `while` line, Bella the last body line). Bella printed line 10 where CPython printed line 9.

#### Suspected, not reproduced
- Backend `_falls_through` (cpp.py:770) still treats every Loop as falling through, while lower.py's version no longer does. The only effect I saw is a dead `return` in the C++, which is harmless.

#### Checked and clean
- Control flow: about 100 random functions (nesting depth up to 4) mixing `for`/`while` with `else`, `break`, `continue`, `return`, `raise`, `try`/`except`/`finally` and `with` (suppressing and not). The 12 to 25 function programs, 3 seeds at 25 functions plus 2 at 12, compiled and ran identically to CPython. A wf-only fuzz of about 120 seeds of 12 functions found nothing apart from the try/else case above. Hand-written cases also matched: break inside `with`, inside `match`, in the `else` of a nested loop, and `continue` in `try`/`finally`. `break` or `return` leaving a `finally` is excluded by D-10.
- Names: about 630 macro and keyword names, plus reserved emitter names and `py`-prefixed names, used as parameters, locals, closure and `nonlocal` cells, globals, `global` in functions and class bodies, functions, class and instance attributes, imported module names, and `import ... as` targets. All compile; `.cpp` files were checked with `-fsyntax-only`. Execution was checked for `ENOENT`, `S_IFMT`, `stdin`, `NULL`, `EOF`, `errno` and `unix`. A cut-down version of the hidden-variable-clash program (user locals named like `_ann1`, `_format0`, `_comp0`) ran identically. Non-ASCII identifiers and `pyf`/`f_f`/`code_f`/`C_m` collisions ran identically.
- Imports: a module that fails and is re-run (old and new closures read their own globals), imports in class bodies, in functions, with `global`/`nonlocal`, and inside `for`/`else`, plus failing `from` imports. `lazy import` at module level inside `if`, `with`, `for` and `while`, with macro-like names. The `lazy import` forms CPython rejects (inside a function, a class or `try`) are cleanly refused with exit 70.
- `M` as a local from `fn->module` and the `constants_made` guard showed no defect in any of these programs.

## compiled str methods (focus `strs`)

#### Searching with `find`, `startswith` and `count` copies the whole string on every call, so scan loops are quadratic
Severity: medium (a normal tokenizer-style loop runs about 2000 times slower than CPython)
Where: runtime/src/str.cpp:25-30 (`cps_of`), called at :117 (find_like), :137 (starts_ends), :318 (count); `strip`, `partition` and `replace` do the same.
Repro (`perfC.py`):
```
s = "ab " * 100000
i = 0
n = 0
while True:
    j = s.find(" ", i)
    if j < 0:
        break
    n += 1
    i = j + 1
print(n)
```
CPython: prints 100000 in about 0.03 s, exit 0.
Bella: prints 100000 after 67 s (about 2 s of that is the build), exit 0.
A combined run with a second loop of `s.startswith("ab", k)` took 2m14s against 0.08 s.
Why: each call widens the entire receiver into a `std::u32string` before it adjusts start and end. CPython searches in place, so a call costs only what it scans.

#### `find`, `rfind`, `index`, `rindex` and `count` say `not NoneType` where CPython says `not None`
Severity: low (a wrong exception message)
Where: runtime/src/str.cpp:62 (`str_argument`), also reached by `replace` at :356-357.
Repro:
```
try:
    "abc".find(None)
except TypeError as e:
    print(e.args)
try:
    "abc".replace(None, "a")
except TypeError as e:
    print(e.args)
```
CPython: `('find() argument 1 must be str, not None',)` and `('replace() argument 1 must be str, not None',)`.
Bella: the same text with `not NoneType`.
The same difference shows for `rfind`, `index`, `rindex`, `count`, and `replace` argument 2.
Why: `_PyArg_BadArgument` in Python/getargs.c prints `"None"` when the argument is `None`, and the type name otherwise. `partition`, `split`, `strip` and `startswith` already match, because their CPython messages use the type name.

#### An `__index__` that returns a non-int gets an old message, in every slice-index and maxsplit/count path
Severity: low
Where: runtime/src/ops.cpp:580, not str.cpp. It shows through `slice_index` and `index_value` in str.cpp.
Repro:
```
class B:
    def __index__(self):
        return "x"
try:
    "abc".find("a", B())
except TypeError as e:
    print(e.args)
try:
    [1][B()]
except TypeError as e:
    print(e.args)
```
CPython: `('B.__index__() must return an int, not str',)` for both.
Bella: `('__index__ returned non-int (type str)',)` for both.
Why: CPython 3.15's `_PyNumber_Index` uses the new wording, which names the class and `__index__()`.

#### Identity differences, low (only `is` shows them)
Where: runtime/src/str.cpp:31 (`make`), :167, :362, :386.
- Empty strings and one-character Latin-1 strings are not shared. In CPython these are all True, and in Bella all False:
  - `"a".strip("a") is ""`
  - `"a".partition("a")[0] is ""`
  - `"ab".split("b")[0] is "a"`
  - `"ab".strip("b") is "a"`
  - `"a".replace("a", "") is ""`
- `"abc".split(None, 0)`, `"abc".rsplit(maxsplit=0)` and `"abc".split(maxsplit=0)` return a list holding the receiver itself. CPython returns a copy, because the reuse shortcut sits inside the split loop and maxsplit=0 skips the loop.
- `x.replace("a", "".join(["a"]))` returns `x` in CPython, because the two one-character strings are the same cached object. Bella returns a copy.
- Where the pattern is not found, `"".partition("a")` and `"".rpartition("a")` return the receiver in all three slots in CPython. Bella returns it in only one slot.

#### Not testable, refused cleanly
- `class S(str)` stops with `not implemented: subclassing the built-in type 'str'`, so I could not run any of the str-subclass cases (receiver, argument, result type, identity). The same refusal applies to `class T(tuple)`, so tuple subclasses in `startswith` and `endswith` were not tested.
- Ints beyond 62 bits, float constants, and unknown keywords to `split` or `replace` also stop with `not implemented`. Huge-index behaviour was tested only up to 2**62-1.

Suspected, not reproduced:
- `find_in` is a naive O(n*m) search. Worst-case needles on megabyte strings could be far slower than CPython's two-way search. A 200000-character receiver with a 100000-character needle still ran in about 2 s.

Checked and clean:
- About 85,000 differential cases against CPython 3.15.2, in `/tmp/claude-1001/-home-nathan-workspaces-nth-bella/3c0181b5-e55a-4b93-8a5d-84682fffa693/scratchpad/rev/strs/` (`bat1.py` to `bat5b.py`, run with `run.sh`).
- Methods: `find`, `rfind`, `index`, `rindex`, `count`, `startswith`, `endswith`, `partition`, `rpartition`, `split`, `rsplit`, `strip`, `lstrip`, `rstrip`, `replace`.
- Receivers and arguments: empty, ASCII, Latin-1, BMP and astral strings, mixed.
- start/end: negative, out-of-range, None, bool, an int subclass, `__index__` objects including ones that raise or return a non-int, and bad types.
- Tuples for `startswith`/`endswith`, including the empty tuple and a bad element.
- `split`/`rsplit` with `sep=None`, an explicit separator and keyword forms, and maxsplit of 0, negative and 2**62-1.
- `replace` with count 0, negative, a keyword, an empty old string, and the same-object shortcut.
- Wrong-type arguments, argument counts, and keyword and positional errors, including calls through the unbound `str.method`.
- Order in which `__index__` is called.
- Whitespace: every code point U+0000 to U+10FFFF (surrogates excluded) was checked against CPython with `split`, `rsplit` and `strip`, and all agree. The whitespace sets, partition semantics and exception types and arguments otherwise matched, apart from the findings above.

## super, metaclasses, dict and int subclasses (focus `classes`)

#### `type.__repr__` calls the metaclass's `__repr__`, so `super().__repr__()` in a metaclass recurses forever
Severity: high
Where: runtime/src/types.cpp:797 (`type_repr` calls `repr_of`); runtime/src/ops.cpp:662-668
Repro:
```python
class M(type):
    def __repr__(cls): return "<" + super().__repr__() + ">"
class C(metaclass=M): pass
print(repr(C))
print(type.__repr__(C))
```
CPython: `<<class '__main__.C'>>`, then `<class '__main__.C'>`, exit 0. Bella: RecursionError, exit 1.
Why: `type.__repr__` must be type's own formatter. Bella re-dispatches to the override. `__str__`, `__hash__`, `__eq__`, `__call__`, `__setattr__` and `__delattr__` in a metaclass behave correctly through `super()`.

#### An int subclass's `super().__hash__()` and `super().__repr__()` return object's, and so do plain ints
Severity: high
Where: runtime/src/types.cpp:1290-1307 (`int` registers only `__new__`; everything else falls through to `object`)
Repro:
```python
class H(int):
    def __hash__(self): return super().__hash__() + 1
    def __repr__(self): return "H(" + super().__repr__() + ")"
    def __str__(self): return "s" + super().__str__()
h = H(5)
print(hash(h), repr(h), str(h))
print((5).__repr__(), (5).__hash__(), (5).__ne__(6), (5).__lt__(6))
```
CPython: `6 H(5) sH(5)`, then `5 5 True True`. Bella: `37543182 H(<__main__.H object at 0x23cdd0d0>) sH(<__main__.H object at 0x23cdd0d0>)`, then `<int object at 0xb> 0 NotImplemented NotImplemented`.
Why: `int.__repr__`, `__hash__`, `__ne__` and `__lt__` resolve to `object`'s versions. `super().__neg__()` in an int subclass raises AttributeError, where CPython has the method.

#### In-place operators ignore `__iadd__`, `__imul__` and `__ior__` on int and dict subclasses
Severity: medium
Where: runtime/src/ops.cpp (the in-place binary path, near line 231)
Repro:
```python
class I(int):
    def __iadd__(self, o): return "iadd"
class D(dict):
    def __ior__(self, o): return "dior"
x = I(1); x += 1; print(x)
d = D(); d |= {}; print(d)
```
CPython: `iadd`, `dior`. Bella: `2`, `{}`.
Why: an int subclass's `__iadd__` is ignored and plain `+` is used. A dict subclass's `__ior__` is ignored too. The same happens for `__imul__` and `__ior__` on int, and for `l[0] += 1` on an element.

#### Sequence repeat and `range` indexing reject an int subclass
Severity: medium
Where: runtime/src/ops.cpp:146-148 (`repeat`)
Repro:
```python
class K(int): pass
print("ab" * K(2), [1] * K(2), K(2) * (1,))
print(range(3)[K(1)])
```
CPython: `abab [1, 1] (1, 1)`, then `1`. Bella: TypeError "can't multiply sequence by non-int of type 'K'", and TypeError for the `range` index.
Why: the count check accepts only a small int, a bool, or an instance with `__index__`, so `IntInstance` is rejected. This hits IntEnum-like use. Slicing and list indexing with `K` work.

#### A mixin after the built-in base overrides the built-in's own methods
Severity: medium
Where: runtime/src/ops.cpp:749 (`overrides_builtin` compares MRO lookups against `int`'s table, which lacks `__repr__`, `__hash__` and `__eq__`)
Repro:
```python
class M:
    def __repr__(self): return "M.repr"
    def __hash__(self): return 77
    def __eq__(self, o): return "M.eq"
    def __add__(self, o): return "M.add"
    def __neg__(self): return "M.neg"
class X(int, M): pass
x = X(5)
print(repr(x), hash(x), x == 5, x + 1, -x)
class Y(dict, M): pass
print(Y(a=1) == {"a": 1})
```
CPython: `5 5 True 6 -5`, then `True`. Bella: `M.repr 77 M.eq M.add M.neg`, then `M.eq`.
Why: `int` and `dict` come before `M` in the MRO, and CPython's own slots win over `M`'s methods.

#### A metaclass `mro()` override is silently ignored
Severity: medium
Where: runtime/src/types.cpp:792 and `make_class`; `type_new` never calls the metaclass's `mro`
Repro:
```python
class O1: x = "O1"
class O2: x = "O2"
class M(type):
    def mro(cls): print("mro called"); return [cls, O2, O1, object]
class T(O1, O2, metaclass=M): pass
print(T.__mro__[1].__name__, T.x)
```
CPython: `mro called`, then `O2 O2`. Bella: `O1 O1`, and `mro` is never called. A `mro()` returning a non-iterable, or a list containing a non-class, raises no TypeError either.

#### No instance layout conflict check between bases
Severity: medium
Where: runtime/src/types.cpp (`solid_base` and `tp_base` are used only for the `__new__` message)
Repro:
```python
class E(int): pass
class F(dict): pass
try:
    class J(E, F): pass
    print("created")
except TypeError as e: print(e)
class X: __slots__ = ("a",)
class Y: __slots__ = ("b",)
class Z(X, Y): pass
```
CPython: `multiple bases have instance lay-out conflict` for both; the `Z` class raises it. Bella: `created`, and `Z` is created. `J()` then fails with an internal `_dict_next() needs a dict`. `class T(Exception, dict)` and `class U(E, X)` are also accepted.

#### Constructors that read a dict subclass with an overridden `__iter__` bypass the override
Severity: medium
Where: set, frozenset, `set.update`, `{*d}` and `dict.fromkeys` constructors
Repro:
```python
class D(dict):
    def __iter__(self): return iter(["x", "y"])
d = D(a=1)
print(set(d), frozenset(d), {*d}, dict.fromkeys(d))
```
CPython: `{'x', 'y'} frozenset({'x', 'y'}) {'x', 'y'} {'x': None, 'y': None}`. Bella: `{'a'} frozenset({'a'}) {'a'} {'a': None}`. `list`, `tuple`, `for`, `join` and unpacking do call the override.

#### `type(name, bases, ns)` called directly sets no `__module__`
Severity: medium
Where: runtime/src/types.cpp:926-927
Repro: `X = type("X", (), {}); print(X.__module__); print(X())`
CPython: `__main__`, then `<__main__.X object at 0x...>`. Bella: AttributeError `__module__`, and `<X object at ...>` without the module in the repr. (TODO.md lists frame-walking as a later step; the failure is still an AttributeError.)

#### A local named `__class__` plus zero-argument `super()` crashes the compiler
Severity: low
Where: pipeline/l2/wf.py:320
Repro:
```python
class A:
    def f(self): return 1
class B(A):
    def f(self):
        __class__ = int
        return super().f()
try: B().f()
except RuntimeError as e: print(e)
```
CPython: `super(): __class__ cell not found`. Bella: `WellFormednessError: B.f: free '__class__' is not in freevars`, exit 1. A parameter named `__class__` does the same.

#### `del self` then `super()` gives the wrong exception
Severity: low
Where: runtime/src/super.cpp:105 and the frontend intrinsic
Repro: `class A:\n def f(self): pass\nclass B(A):\n def f(self):\n  del self\n  super()` then `B().f()`.
CPython: RuntimeError `super(): arg[0] deleted`. Bella: UnboundLocalError `self`.

#### Smaller differences, each confirmed
Severity: low
- `object.__init_subclass__` with kwargs raises `__init_subclass__() takes no keyword arguments` where CPython says `Z2.__init_subclass__() takes no keyword arguments` (class name prefix missing).
- A `__set_name__` that raises lacks the note `Error calling __set_name__ on 'BadSN' instance 'a' in 'Z3'` in `__notes__`.
- An MRO conflict lists all bases (`P1, O, P2`) where CPython lists only `O, P2`.
- `super(B).__get__(None, None)` returns self instead of raising TypeError `__get__(None, None) is invalid`.
- `type("a\0b", (), {})` raises no ValueError.
- `type("X", (), {}, 3)` reads `type.__new__() takes exactly 3 arguments (4 given)` where CPython says `type() takes 1 or 3 arguments`.
- `type("X", (), [])` says `must be dict` where CPython says `must be dict or frozendict`.
- `Y(3)` for a `type` subclass prints `<class 'Q'>` with no module.
- `E(1, 2, 3)` for an int subclass gives `int expected at most 2 arguments, got 3` where CPython says `int() takes at most 2 arguments (3 given)`.
- `[1, 2, 3][C]` with `__index__` on C's metaclass raises TypeError where CPython indexes.
- `del int.real` says `cannot delete` where CPython says `cannot set`.
- `build_class()` appears where CPython writes `__build_class__()`.
- `repr(slice(1, 2))` prints `<slice object at 0x...>`.

Suspected, not reproduced:
- `__set_name__` iterates the live `c->attrs.items()` (types.cpp:543). A `__set_name__` that adds or deletes attributes worked in my test, so I could not show a fault.
- Cyclic garbage with `__del__` is never collected (no GC), which is a known gap.

Checked and clean:
- Zero- and two-argument `super` in instance methods, classmethods, staticmethods, nested functions, lambdas, comprehensions, closures and rebound first arguments.
- `super` with property, descriptor, `__setattr__`, `__getattr__` and `__slots__`, a super object's repr and fields, and `supercheck` errors.
- Metaclass conflicts, `__prepare__` oddities, `__new__` and `__init__` with kwargs, `__call__` overrides, `__init_subclass__` and `__set_name__` order, `__mro_entries__`, `__instancecheck__` and `__subclasscheck__`, `__abstractmethods__`, and descriptor precedence on a metaclass. Metaclass operator dispatch is clean except the `__index__` case above.
- `int(s, base)`: about 72,000 generated cases (strings up to 4 characters over 13 symbols, 7 bases) matched CPython. Messages, constructor arguments and `__int__` handling also matched. Values beyond 62 bits are refused.
- Dict subclasses: overridden `__getitem__`, `__setitem__`, `__missing__`, `keys`, `__contains__`, `__len__`, `__eq__` and `get`; `update`, `dict()`, `**` and `|`; `__prepare__` namespaces.

## RL-228 to RL-255 re-tested (focus `remediation`)

Review of d614f7c (RL-228 to RL-255), compiled against CPython 3.15.2. The core fixes hold, but I found eleven defects in the same code paths or beside them. Programs are in scratchpad/rev/remediation/ (that is /tmp/claude-1001/-home-nathan-workspaces-nth-bella/3c0181b5-e55a-4b93-8a5d-84682fffa693/scratchpad/rev/remediation/). Source lines in tracebacks are omitted from Bella's reports, so I ignored that difference.

#### dict.popitem looks the key up again, so it can call `__eq__` and remove the wrong entry
Severity: medium
Where: runtime/src/call.cpp:802-815 (`dict_popitem_m` calls `dict_pop(d, key, hash)`)
Repro:
```python
yes = []
class M:
    def __init__(self, n): self.n = n
    def __hash__(self): return 7
    def __eq__(self, o): return True if yes else self is o
    def __repr__(self): return "M" + str(self.n)
d = {M(1): 1, M(2): 2}
yes.append(1)
print(d.popitem()); print(d)
```
CPython: `(M2, 2)` then `{M1: 1}`, exit 0. Bella: `(M2, 1)` then `{M2: 2}`, exit 0.
Why: CPython's popitem takes the last entry by index and never compares. This is the same flaw RL-234 fixed in `pop`. With an `__eq__` that raises, Bella raises from `popitem` where CPython returns the pair (`p1.py`).

#### `in` fails for iterators and for mappingproxy (`"x" in C.__dict__`, `"x" in vars(C)`)
Severity: medium
Where: runtime/src/ops.cpp:~383-411, `contains()`. The builtin-iterator and `Kind::Proxy` cases fall through to the final "not a container or iterable" raise. I could not tell whether d614f7c introduced this.
Repro:
```python
class C: x = 1
print(1 in iter([1, 2]))
print("x" in C.__dict__)
```
CPython: `True`, `True`, exit 0. Bella: `TypeError: argument of type 'list_iterator' is not a container or iterable`, exit 1. The second line fails the same way with `mappingproxy`. `mappingproxy.__contains__` is registered at types.cpp:1354 but never reached.

#### `set.__contains__`, `remove` and `discard` reject a set key (RL-249 neighbour)
Severity: medium
Where: runtime/src/core.cpp:440 and set.cpp:129-132 (`set_key_hash` and `set_contains` take no frozenset fallback)
Repro:
```python
fs = frozenset({1, 2})
print({1, 2} in {fs})
s = {fs}; s.remove({1, 2}); print(s)
```
CPython: `True`, `set()`, exit 0. Bella: `TypeError: cannot use 'set' as a set element (unhashable type: 'set')`, exit 1.
Why: CPython's `set_contains`, `remove` and `discard` temporarily turn a set key into a frozenset. This also fails for `in` on an empty set or frozenset.

#### Comprehension inside a lambda that sits in a loop gives NameError
Severity: high, but outside my focus and not from this commit. It broke several of my test harnesses.
Repro:
```python
def t(f): print(f())
for n in (1, 2):
    t(lambda: [i for i in range(3)])
```
CPython: `[0, 1, 2]` twice. Bella: `NameError: name '_comp0' is not defined`, exit 1.
Why: the helper is not hoisted when the lambda is in a `for` or `while` body. A lambda outside any loop works.

#### `del lst[:1]` raises a nonsense TypeError
Severity: medium
Repro: `l=[1,2,3,4]; del l[:1]; print(l)`
CPython: `[2, 3, 4]`. Bella: `TypeError: list assignment indices must be integers or slices, not slice`, exit 1. A refusal would have been acceptable.

#### Too-many-positional is checked before bad keywords (RL-240 neighbour)
Severity: low
Repro: `def f(a): pass` then `f(1, 2, z=1)`; also `f(1, 2, a=1)`.
CPython: `f() got an unexpected keyword argument 'z'`, and for `a=1` `got multiple values for argument 'a'`. Bella: `f() takes 1 positional argument but 2 were given`.
Why: CPython processes keywords first. This also affects methods, `__init__`, keyword-only parameters (`g(1,2,k=1,z=2)`) and `W(1, z=1)`.

#### Several built-in `T.__new__(X)` calls skip tp_new_wrapper's checks (RL-244 neighbour)
Severity: low
CPython raises TypeError for each of these. Bella gives:
- `ValueError.__new__(Ex)` with `class Ex(Exception)`, and `KeyError.__new__(ValueError)`: accepted, returns an instance (CPython: "not a subtype of ValueError", and "LookupError.__new__(ValueError)" for the KeyError case).
- `object.__new__(Ex)`: accepted (CPython: "is not safe, use Ex.__new__()").
- `int.__new__(bool)`: returns 0 (CPython: "is not safe, use bool.__new__()").
- `bool.__new__(int)`: returns 0 (CPython: "not a subtype of bool").
- `type.__new__(type, 1)`: returns `<class 'int'>` (CPython: "takes exactly 3 arguments (1 given)").
- `list.__new__(list)`, `tuple.__new__(tuple)` and `str.__new__(str, 5)`: "object.__new__(list) is not safe, use list.__new__()" instead of working. `list.__new__()` and `list.__new__(1)` name `object.__new__` in the message instead of `list.__new__`.

#### `AttributeError(name=..., obj=...)` and `NameError(name=...)` reject keywords (RL-230 neighbour)
Severity: low-medium
Repro: `print(AttributeError("m", name="n", obj=3).name)`
CPython: `n`. Bella: `TypeError: AttributeError() takes no keyword arguments`, exit 1.
Why: the fields exist as natively modelled members but cannot be set at construction. This also breaks `e.__init__(..., name=...)`, subclasses, and `raise AttributeError("x", name=..., obj=...)` inside `__getattr__`. An unknown keyword should say "got an unexpected keyword argument 'zz'".

#### `__bool__ = None` and `__next__ = None` do not follow RL-245
Severity: low
- `class L: __bool__ = None`, then `bool(L())`. CPython: `TypeError: 'L' cannot be interpreted as a boolean`. Bella: `'NoneType' object is not callable`.
- A class with `__next__ = None` and `__iter__` returning self, then `next(obj)`. CPython: `'NoneType' object is not callable`. Bella: `'K' object is not an iterator`.

#### Wrong wording for non-iterable and non-integer objects
Severity: low
- `[*x]` where `x.__iter__ = None` or x is not iterable: CPython says "Value after * must be an iterable, not X"; Bella says "'X' object is not iterable".
- `"".join(x)` for a non-iterable x: CPython says "can only join an iterable".
- `[1][obj]`: CPython says "list indices must be integers or slices, not X"; Bella says "'X' object cannot be interpreted as an integer".
- An `__iter__` returning an int: CPython says "X.__iter__() must return an iterator, not int"; Bella says "iter() returned non-iterator of type 'int'".
- `{}.update(obj)` with `keys()` returning an int: CPython says "X.keys() must return an iterable, not int".
- A class whose `__getattr__` is None, passed to `dict()`: Bella reports "'Oc' object is not iterable" where CPython says "'NoneType' object is not callable".

#### Non-string class `__module__` is reported differently
Severity: low
Repro: `class E(Exception): pass`, then `E.__module__ = 5`, then `raise E("x")`.
CPython: the report line is `<unknown>.E: x`. Bella prints `E: x`.

Suspected, not reproduced: none.

Checked and clean (results identical to CPython):
- Exception fields: args, `__cause__`, `__context__`, `__traceback__` and `__suppress_context__`, covering type checks, deletion, `vars()`, the order in which fields die (via `__del__`), `with_traceback`, and slots subclasses. Also stores to absent fields (RL-255) across Exception and the classes that are not refused.
- Context handling: about 20 chain and cycle scenarios, including finally, with-exit, loops, self-raise, `from` with bad causes, pre-set contexts, and 2- and 3-cycles.
- Uncaught and unraisable reports: raising or non-str `__str__`, a SystemExit or KeyboardInterrupt inside `__str__`, `__qualname__`, multi-line messages, cause and context cycles.
- `except` clause type checks: tuples, nested tuples, metaclass `__instancecheck__`, evaluation order.
- Dict operations: hash and `__eq__` call counts for get, `in`, setitem, setdefault, pop, del, copy, `update`, `|`, `**`, fromkeys, `dict()` and `==`. Mutation (clear, grow, delete, replace) during lookup, comparison and update. Iterator mutation scenarios for dict and set. Leaks and destruction order when `__eq__` or `__hash__` raises (23 cases).
- Unhashable-key wording across about 30 dict and set entry points.
- Lists: mutation during `__eq__` in remove, count, index, in, `==`, `!=`, `<`, `<=` and `>`, with six mutation kinds at three positions, plus persistent mutators. Also extend and `+=` with self, and `pop` and `insert` with a mutating `__index__`.
