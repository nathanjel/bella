# Python → C++26 converter: dialect specification v0

Oct 30, 2026 · @Marcin Gałczyński

## 1. Scope and status

This specification defines the Python dialect the converter accepts and the behaviour a compiled program must show, so that correctness is checked against CPython rather than argued about. It is normative: MUST, MUST NOT and MAY carry their RFC 2119 meaning; everything else is explanation. This is v0.5: the decisions of section 12 (taken on 2026-10-30, decision 15 revised on 2026-11-01) and the import-guard and traceback decisions of 2026-11-01 (section 7) are folded into the register and the sections; it becomes v1 when the conformance corpus of section 10 exists.

The reference implementation is CPython 3.15.2, pinned (moved from 3.14.8 in v0.4, section 13); moving the pin is a revision of this document, because exact exception text and cached artefacts depend on it. Where this document is silent, CPython 3.15.2's behaviour is the specification; where CPython's behaviour is unspecified or varies between runs, section 2 says whether a compiled program must match a particular choice.

Every construct carries a scope marker: \[P1\] is in the constrained first release (design document, section 13), \[P2+\] arrives in a later phase, \[X\] is excluded from the dialect. A \[P2+\] construct compiles to a clear error in phase 1, never to a silent approximation.

Relation to the other documents: the [feasibility study](https://claude.ai/artifact/A8j484xiYfh9VveHh1wod1) says why the approach works, the [design document](https://claude.ai/artifact/85e8947GSEJ2bgafhvrDYr) says how the converter is built, and this document says what correct means for a compiled program. On semantics this document wins; on mechanism the design document wins.

## 2. Observational equivalence

A compiled program is equivalent to the same program under CPython 3.15 when, for every input, both produce the same observable trace. The trace is the list below; a difference outside it is not a defect, and every difference inside it is a defect or a registered deviation (section 11).

| Observable: a compiled program MUST reproduce | Detail |
| --- | --- |
| Standard output and standard error | Byte for byte, except traceback lines (D-06: file and line only in release builds) and the runtime-generated wording of built-in exception messages (D-08), which the harness masks per exception type |
| Exit status | Including `SystemExit` codes and the status after an uncaught exception |
| Values and mutations | The value returned by every call, and the sequence of mutations applied to every argument, container and global, in program order |
| Exceptions | The class of every exception raised; its structured and user-supplied payload (user arguments passed to a built-in exception's constructor, `KeyError`'s key, `OSError`'s `errno` and `filename`, `StopIteration.value`, the fields of `UnicodeError`, the `name` of `AttributeError`, `NameError` and `ImportError`); its `__cause__` and `__context__` chain; whether it was suppressed; and the point at which it was raised. Only the runtime-generated human-readable wording of a built-in exception is exempt (D-08) |
| Effects on the outside world | Files written, sockets, subprocesses, environment changes and signals, in order |
| Container iteration order | `dict` (insertion order) and `list`/`tuple` always; `set` and `frozenset` whose elements hash by value (D-05); never for identity-hashed elements, whose order varies between CPython runs too |
| `repr` and `str` of every built-in type | Including shortest round-trip floats, the `__format__` mini-language and integer digit limits (section 6) |
| `hash()` of built-in types | `int`, `float` (except NaN), `str` and `bytes` for a given seed, `tuple`, `frozenset`, with CPython's formulas (section 6). Hashes derived from identity (NaN, objects without `__hash__`) are unobservable in value but MUST be stable within a run and consistent with `==` |
| Finaliser timing for objects not on a reference cycle | `__del__`, `__exit__`, weak-reference callbacks and file closes run when the last reference is dropped, synchronously, in CPython's order |
| Evaluation order | Left to right in every expression, argument list, comprehension and chained comparison, with each operand evaluated once |

| Declared unobservable: MAY differ | Reason |
| --- | --- |
| `id()` values and the addresses inside default reprs (`<Foo object at 0x...>`) | Implementation addresses (D-01, D-02), compared up to a consistent renaming within one run: every equality and inequality CPython shows between address-derived values MUST hold in the compiled program; only the numbers may differ |
| `is` between equal small-integer immediates and between equal interned strings | More often true than in CPython; CPython already warns about code that depends on it (D-03) |
| The moment a reference cycle is collected, and the finaliser order among its members | Collector timing (D-04) |
| Finalisation order of module globals at interpreter exit | Unspecified in CPython too (D-07) |
| `sys.getsizeof` values, memory addresses, allocation counts | Implementation detail |
| Thread interleavings | Nondeterministic in CPython too; \[P2+\] |
| Traceback line text | Decision D-06; the exception type and message are observable |
| Performance, memory footprint, start-up time | Not semantics |

Two consequences. A program that decides on the numeric value of a second-table item is outside the guarantee, while a decision on an identity relationship (a is b, membership in an identity-keyed dictionary) is inside it, because relationships are preserved under renaming; `bella-lint` reports the read. And the conformance harness (section 10) compares exactly the first table, nothing more, so a passing program is one whose first-table trace matches CPython on the corpus and on generated inputs.

## 3. Accepted language

The grammar is CPython 3.15's, frozen for phases 0 to 2 (decision 15, revised in v0.4). Every construct below keeps CPython's semantics unless the Semantics column says otherwise; the marker says when it is available.

| Area | Constructs | Scope | Semantics |
| --- | --- | --- | --- |
| Statements | Assignment to every target form (tuple and starred unpacking, subscripts, attributes, walrus, augmented, annotated); `del`; `pass`; `if`, `while`, `for` with `else`; `break`, `continue`; `return`; `raise` and `raise from`; `try`/`except`/`except*`/`else`/`finally`; `with`; `def`, `class`, `lambda`; `global`, `nonlocal`; `import` forms; `assert`; `match` | \[P1\] | As CPython. `assert` is active by default; a build-profile switch that strips assertions and makes `__debug__` false is planned as the `-O` equivalent (D-09, \[P2+\]). `return`, `break` or `continue` leaving a `finally` block is a compile-time error (D-10) |
| Statements, async | `async def`, `await`, `async for`, `async with`, `async` comprehensions | \[P2+\] | As CPython once the async milestone lands |
| Expressions | All operators and their dunders; chained comparisons; `and`/`or` returning operands; conditional expressions; comprehensions of all four kinds; generator expressions; `yield` and `yield from`; starred and double-starred unpacking in calls and literals; slicing with negative and omitted bounds; f-strings; t-strings (PEP 750) | \[P1\] | Left-to-right evaluation, each operand once; `a < b < c` evaluates `b` once; `x or y` has the type of the operand it returns. Unpacking inside a comprehension or generator expression (`[*xs for xs in rows]`, `{**d for d in ds}`, PEP 798, new in 3.15) is \[P2+\]: no phase-1 library module uses it, and it waits until ordinary comprehensions are lowered with their scope intact |
| Functions | Positional-only, keyword-only, defaults (evaluated once at definition), `*args`, `**kwargs`, closures with cells, `nonlocal`, decorators, recursion, `functools.wraps` metadata | \[P1\] | Defaults are shared across calls as in CPython; `__name__`, `__qualname__`, `__doc__`, `__module__`, `__defaults__`, `__kwdefaults__`, `__wrapped__` readable |
| Functions, reflection | `__annotations__` and `annotationlib` (PEP 649 lazy evaluation), `__code__`, `__globals__`, `__closure__` | \[P2+\] for annotations; \[X\] for `__code__` (section 4) | Annotations are evaluated lazily by the staged metadata, in CPython 3.15's `Format` modes |
| Classes | Single inheritance; multiple inheritance with stateless mixins; C3 MRO; `super()`; `__slots__`; properties; `classmethod`, `staticmethod`; descriptors by the data-descriptor rules; `__init_subclass__`, `__set_name__`, `__class_getitem__`; class decorators; class-body code | \[P1\] | Class bodies and metaclasses run at staging when they are stageable (section 8); a class created from runtime values is \[P2+\] |
| Classes, later | Stateful multiple inheritance; metaclasses that depend on runtime values; `__class__` assignment; `__getattribute__` overrides; `type(name, bases, ns)` at runtime | \[P2+\] | As CPython; CPython's layout-compatibility rule for `__class__` assignment |
| Attribute access | Literal names; `getattr`, `setattr`, `delattr`, `hasattr` with computed names; `__getattr__`; `__setattr__`, `__delattr__`; `__dict__` and `vars()` as a real dictionary with stable identity and an independent lifetime, including `obj.__dict__ = d` and two objects sharing one dictionary; an instance has a `__dict__` exactly when its class's layout inherits one: `object` and the other built-in bases provide none, a class defined without `__slots__` adds one, and a class with `__slots__` adds one only if `'__dict__'` is listed, so a fully slotted hierarchy has none and `__slots__ = ()` under an unslotted base keeps the base's | \[P1\] | Lookup order: data descriptor, instance storage, non-data descriptor or class attribute, `__getattr__`, `AttributeError` (design document, section 3); `__getattr__` runs whenever the generic lookup raises `AttributeError` (an unset slot, a descriptor or property that raises it), not only for an absent name (C-3-09) |
| Data model | Every operator and container dunder; numeric protocol with `NotImplemented` and reflected operands; `__bool__`/`__len__` truthiness; `__hash__`/`__eq__` interplay (defining `__eq__` without `__hash__` makes instances unhashable); `__repr__`, `__str__`, `__format__`; `__call__`; `__iter__`/`__next__`; `__enter__`/`__exit__`; `__index__`, `__round__`, `__int__`, `__float__`; `__del__`; `__weakref__` | \[P1\] | As CPython, including `__del__` running once per object (PEP 442) and resurrection |
| Data model, later | Pickling (`__reduce__`, `__getstate__`, `__setstate__`); the buffer protocol; `__class_getitem__` on user generics at runtime beyond staging | \[P2+\] | As CPython |
| Exceptions | The full built-in hierarchy; user exception classes; chaining with `__cause__`/`__context__` and `__suppress_context__`; `except*` and exception groups; `finally` semantics including replacement exceptions; `with` suppression when `__exit__` returns true; `__traceback__` as an opaque object | \[P1\] | Built-in exception message text may differ from CPython's for now (D-08); `traceback` formatting from source maps gives file and line in release builds and CPython's format in debug builds (D-06) |
| Generators | Generator functions and expressions; `send`, `throw`, `close`; return values via `StopIteration.value`; `yield from` delegation; finalisation by `close()` on the last reference, `GeneratorExit` | \[P1\] | As CPython |
| Imports | Absolute and relative imports; `from m import a as b`; `import a.b.c`; packages with `__init__`; `__all__`; module `__getattr__` and `__dir__` (PEP 562); `importlib.import_module` with any name inside the closed world; `sys.modules` reads; `lazy import` and `lazy from ... import` at module scope and `__lazy_modules__` (PEP 810, new in 3.15) | \[P1\] | Initialised at the first import statement that reaches the module, by the state machine of section 8; `ModuleNotFoundError` for a module outside the closed world. Lazy imports are \[P1\] because the phase-1 library uses them (section 7): the statement binds a proxy (`types.LazyImportType`, visible through `globals()`), the module is initialised at the first use of the name, and its import errors are raised there; `lazy import` inside a function, a class body or a `try` statement is a `SyntaxError`, as in CPython |
| Scoping | LEGB resolution; class-scope rules; comprehension scoping as in 3.12 and later (PEP 709); `global`/`nonlocal`; `del` of a local or a global; `locals()` as a fresh mutable dictionary inside functions (PEP 667) | \[P1\] | A bare name bound nowhere in its scope chain and not a builtin is a compile-time `NameError`. At runtime a global name resolves to the module global if it is bound at that moment, else to the builtin of the same name, else raises `NameError` (so a module that assigns and later deletes `len` sees the builtin again); an unbound local raises `UnboundLocalError`; writes to the dictionary returned by `locals()` do not change the function's variables |
| Modules | `__name__`, `__doc__`, `__all__`, `__file__` (D-12), `__spec__` with `name` and `origin` only, `__package__` | \[P1\] | `__file__` is the recorded source path from the build |
| Builtins | Every built-in function and type except those in section 4, except `memoryview` \[P2+\], and except `help`, `exit`, `quit`, `copyright`, `credits` and `license`, which `site` adds and the closed world does not; `open`, `input`, `print`, `iter`/`next`, `isinstance`/`issubclass` including ABC hooks, `super`, `type`, `complex`, `zip(strict=)`, `sorted` with keys, `round`, `format`, and the 3.15 additions `frozendict` (PEP 814) and `sentinel` (PEP 661), whose commitments are in section 6 | \[P1\] | Builtins are bound at compile time; shadowing by a module global or a local is honoured statically; `breakpoint()` is a no-op that prints a warning (D-11) |
| Threads, processes, signals | `signal` in the main thread; `atexit`; `os.fork` | \[P1\] for `signal` and `atexit`, \[P2+\] for `os.fork`, `threading`, `multiprocessing` | The phase-1 runtime is single-threaded; `threading` imports the shim of section 7, and creating a thread raises with the milestone's name |

## 4. Excluded constructs

Each exclusion is a compile-time error with an id, reported at the file and line that uses it; `bella-lint` reports the same ids before the compiler runs. Nothing on this list is approximated at runtime.

| Id | Excluded | Rationale |
| --- | --- | --- |
| E-01 | `eval`, `exec`, `compile` applied to source text at runtime; `builtins.__build_class__` called directly | Requires an interpreter; the embedded-CPython island is the only route for a package that needs it |
| E-02 | Frame and code introspection: `sys._getframe`, `inspect.currentframe`, `inspect.stack`, `inspect.getsource` at runtime, frame objects and their attributes, `types.CodeType`, `__code__`, `dis`, bytecode of any kind | No frames and no bytecode exist in a compiled program |
| E-03 | Tracing and profiling hooks: `sys.settrace`, `sys.setprofile`, `sys.monitoring`, `threading.settrace`, `bdb`, `pdb`, `cProfile`, `profile`, `profiling` (PEP 799, new in 3.15; `cProfile` is now its alias), `tracemalloc` | Interpreter instrumentation |
| E-04 | Import-system customisation: `sys.meta_path`, `sys.path_hooks`, finders and loaders from `importlib.abc`, replacing `__import__`, `importlib.reload`, `sys.set_lazy_imports`, `sys.set_lazy_imports_filter`, writes to `sys.modules`, writes to `sys.path`, `.pth` and `site` customisation | The closed world is resolved at build time (section 8) |
| E-05 | CPython internals: `ctypes.py_object`, `ctypes.pythonapi`, `gc.get_objects`, `gc.get_referrers`, `gc.get_referents`, `sys.getrefcount`, `object.__reduce_ex__` tricks that rely on `copyreg` internals | No CPython object graph exists |
| E-06 | Assignment to attributes of the `builtins` module, and assignment to attributes of built-in types | Builtins are bound at compile time; CPython already rejects the second |
| E-07 | Creating functions from code objects (`types.FunctionType(code, ...)`), `exec`-based templating at runtime | Same reason as E-01 |
| E-08 | `doctest`, `code`, `codeop`, `timeit` with string statements, `pydoc` interactive use | Built on E-01. `traceback` imports a `codeop` shim (section 7); a program's own use of `codeop` is still this error |

The staging exemption. The exclusions apply to code that would run in the compiled program. Definition-time uses of `exec` and `eval` inside the standard library (`dataclasses` building `__init__`, `collections.namedtuple` building `__new__`, `enum` and `typing` machinery) run once at build time in the host CPython under the staging contract of section 8; their results are snapshotted and compiled, and the strings they executed never exist in the program. A library that uses E-01 at runtime, not at definition time, is not stageable and must go to the island or be replaced.

What is deliberately not excluded: `__getattr__`, `__getattribute__`, `__setattr__`, computed-name attribute access, class mutation, `__class__` assignment, runtime class creation, `importlib.import_module` with a computed name, `globals()` and `vars()`. These are tiers with a cost (section 5), never errors.

## 5. Tiers in the first release

The design document's section 7 defines the tiers and their mechanisms; this section fixes which of them a phase-1 program may use. A \[P2+\] tier compiles to an error naming the milestone, not to a slower path.

| Feature | Tier | Phase 1 |
| --- | --- | --- |
| Literal attribute names on declared fields; names first assigned outside `__init__` (layout widening) | 0 | Yes |
| `__getattr__`; `__setattr__` and `__delattr__` overrides | 1 (2 for the overrides) | Yes |
| A method assigned on a class (`Cls.f = g`); `setattr(Cls, "literal", v)` | 1 | Yes |
| `getattr`, `setattr`, `delattr`, `hasattr` with computed names; `vars()` and `__dict__` as a live mapping | 2 | Yes |
| `setattr(Cls, computed, v)`, class `__dict__` writes | 2 | Yes |
| `importlib.import_module(computed)` inside the closed world | 2 | Yes |
| `globals()[name]` reads and writes of statically bound names | 2 | Yes |
| `__getattribute__` overrides | 2 | \[P2+\] |
| `obj.__class__ = Other` | 1 | \[P2+\] |
| `type(name, bases, ns)`; class bodies that depend on runtime values | 3 | \[P2+\] |
| Stateful multiple inheritance | 3 | \[P2+\] |
| Threads, `async`, the island, native (unboxed) representations beyond trivial proofs | not a tier | \[P2+\] |

The lint report for a program lists every use of tier 1 to 3 with its file, line and tier, so the author knows the cost before the first build; a tier-2 access in a hot loop is a warning, not an error.

## 6. Built-in types: exact commitments

Where CPython's choice is observable through `repr`, `hash`, ordering or iteration, the compiled runtime MUST make the same choice; the table names the algorithm so that the runtime can be checked against CPython's source rather than its output alone.

| Type | Commitment |
| --- | --- |
| `int` | Unbounded magnitude; `bool` is a subclass with `True == 1`; `//` and `%` floor toward minus infinity and `%` takes the divisor's sign; `divmod`, three-argument `pow`, `**` with a negative exponent returning `float`; bitwise operators on an infinite two's-complement representation; `hash(n) == n % (2**61 - 1)` with the sign kept and `hash(-1) == -2`; `str(n)` and `int(s)` for any size with underscores and bases 2 to 36; `sys.set_int_max_str_digits` with CPython's default of 4300; `bit_length`, `bit_count`, `to_bytes`, `from_bytes`, `is_integer`; `OverflowError` when converting to `float` beyond its range; `ZeroDivisionError` raised where CPython raises it (message text per D-08) |
| `float` | IEEE 754 binary64; shortest round-trip `repr`; `round()` to even; `hash` by CPython's `_Py_HashDouble` so that `hash(2.0) == hash(2)`; `nan` and `inf` semantics including `nan != nan`; `-0.0` preserved; the `__format__` mini-language in full; mixed comparison with `int` exact (`2**53 + 1 == 2.0**53` is `False`); `math.fsum` correctly rounded |
| `complex` | As CPython, including `repr` forms and `hash` |
| `str` | Immutable sequence of code points with O(1) indexing, in CPython's PEP 393 representation (Latin-1, UCS-2 or UCS-4 chosen per string; decision 3, D-13) with a UTF-8 copy cached on demand for C libraries; all methods including `casefold`, `isidentifier`, `translate`, `format`, `%`; `str.__hash__` is SipHash-1-3 keyed by the process seed, `PYTHONHASHSEED` honoured (D-14); surrogate code points allowed, `surrogateescape` at OS boundaries; `unicodedata` tables are \[P2+\] |
| `bytes`, `bytearray` | All methods; `hash(bytes)` by the same SipHash; `memoryview` and the buffer protocol are \[P2+\] |
| `list` | `sort` is stable and evaluates `key` once per element, as timsort does; `list.sort` with `reverse` keeps stability; slice assignment and deletion with steps; `IndexError` and `ValueError` raised where CPython raises them (message text per D-08) |
| `tuple` | `hash` by CPython's `tuplehash` (the xxHash-derived algorithm of 3.8 and later), so `hash((1, 2))` matches |
| `dict` | Insertion order, including after deletions and re-insertions; `popitem` is LIFO; views; \` |
| `set`, `frozenset` | Element semantics as CPython; `hash(frozenset)` by CPython's algorithm; iteration order per decision D-05 |
| `frozendict` | Immutable mapping (PEP 814, new in 3.15), not a `dict` subclass; insertion order kept for iteration and `repr`, ignored by `==`; hashable when every key and value is, with CPython's hash, which equals `hash(frozenset(items))` |
| `range`, `slice`, `enumerate`, `zip`, `reversed`, `map`, `filter` | As CPython, including `zip(strict=True)` errors and `slice.indices` |
| `object` | Default `__eq__` is identity; default `__hash__` is derived from identity (value unobservable, D-01); default `__repr__` is `<module.Class object at 0x...>` with the address unobservable (D-02) |
| `type` | `isinstance` and `issubclass` honour `__instancecheck__` and `__subclasscheck__` (ABCs work); `__mro__`, `__bases__`, `__name__`, `__qualname__`, `__module__`, `__subclasses__()` (complete, because the world is closed) |
| `None`, `NotImplemented`, `Ellipsis`, `True`, `False` | Singletons; `type(None)` is `NoneType`; `NotImplemented` drives reflected operators as CPython does |
| `sentinel` | Named unique marker (PEP 661, new in 3.15): `repr` is its name, it compares equal only to itself, and `copy` and `deepcopy` return the same object; pickling it is \[P2+\] with the rest of pickling (section 3) |
| Numeric tower | `int` op `float` promotes to `float` with correctly rounded conversion; `int` op `complex` likewise; comparisons across the tower are exact; `math` domain errors raise `ValueError` where CPython does (message text per D-08) |

## 7. Standard library status

A module is compiled (its pure-Python source goes through the converter), mapped (its C implementation is replaced by a runtime facility or a licensed library), later (\[P2+\]), or excluded (\[X\], section 4). Pure-Python fallbacks that CPython ships beside C accelerators (`_pydatetime`, `_pydecimal`, `_pyio`) are compiled as ordinary modules.

| Group | Modules | Status |
| --- | --- | --- |
| Core data | `collections` (with `keyword` and `reprlib`, which it imports), `itertools`, `functools`, `operator`, `enum`, `dataclasses`, `typing`, `abc`, `copy`, `copyreg`, `types`, `contextlib`, `weakref`, `contextvars` (single-threaded implementation), `bisect` | \[P1\]; C parts mapped, Python parts compiled, `dataclasses`, `enum` and `typing` through staging |
| Text | `string`, `re`, `textwrap`, `difflib`, `json`, `csv`, `struct`, `base64`, `binascii`, `codecs` (UTF-8, Latin-1, ASCII, UTF-16/32), `html`, `urllib.parse` | \[P1\]; `re` mapped onto PCRE2, `json` onto yyjson, `struct` onto the runtime; `unicodedata` and the full codec registry \[P2+\] |
| Numbers | `math`, `cmath`, `decimal` (via `_pydecimal`), `fractions`, `random` (bit-exact Mersenne Twister and CPython's distribution algorithms), `statistics` (imports `bisect`, listed above), `numbers` | \[P1\] |
| Dates | `datetime` (via `_pydatetime`), `time`, `calendar` | \[P1\]; `zoneinfo` \[P2+\] |
| Files and OS | `os`, `os.path`, `pathlib`, `io`, `shutil` (its optional `bz2` and `lzma` imports resolve to `ImportError` in phase 1), `tempfile`, `glob`, `fnmatch`, `stat`, `errno`, `sys` (section 8 lists the supported subset) | \[P1\]; mapped onto POSIX and `<filesystem>` |
| Process and signals | `signal` (main thread), `atexit` | \[P1\] |
| Process and signals, later | `subprocess`, `os.fork`, `multiprocessing` | \[P2+\] |
| Concurrency | `threading` (real threads), `queue`, `concurrent.futures`, `asyncio`, `selectors` | \[P2+\] (the threads and async milestones). `threading` ships in phase 1 as a single-threaded shim (locks, `local`, `current_thread`, `Event`, no thread creation) because `logging` and others import it at module level; creating a thread raises with the milestone's name |
| Network | `socket`, `ssl`, `http.client`, `http.server`, `urllib.request`, `email`, `smtplib` | \[P2+\]; pure-Python parts such as `email` compile earlier where their dependencies allow |
| Persistence and compression | `pickle`, `shelve`, `sqlite3`, `dbm`, `zipfile`, `tarfile`, `gzip`, `zlib`, `bz2`, `lzma`, `compression.zstd` | \[P2+\]; `zlib` \[P1\] |
| Hashing and security | `hashlib`, `hmac`, `secrets`, `uuid` | \[P1\]; mapped onto BearSSL or libsodium |
| Development | `logging`, `argparse`, `warnings`, `unittest` (needed by the conformance corpus itself), `pprint`, `traceback` (formatting from source maps), `inspect` (`signature`, `getmembers`, `isclass` and relatives from staged metadata) | \[P1\] for `logging` (its `findCaller` takes call-site information the compiler supplies, replacing `sys._getframe`), `argparse`, `warnings`, `unittest`, `pprint`, and `traceback` formatting from source maps (needed by `logging` and `unittest`); \[P2+\] for `inspect`; frame functions of `inspect` \[X\] |
| Internationalisation | `locale` (C and UTF-8 locales), `gettext` | `gettext` and the C/UTF-8 subset of `locale` are \[P1\] because `argparse` imports them; the rest of `locale` is \[P2+\] |
| Excluded | `code`, `codeop`, `dis`, `bdb`, `pdb`, `doctest`, `tracemalloc`, `cProfile`, `profile`, `profiling`, `sys.monitoring`, `ctypes.pythonapi` | \[X\] (section 4) |

The phase-1 set is a dependency-closed manifest, not a list of names: every module marked \[P1\] has every import it executes at runtime marked \[P1\] as well, with the adaptation named here where the dependency would otherwise be later or excluded (`threading` shim, single-threaded `contextvars`, `copyreg`, `gettext` with the `locale` subset, `traceback` formatting, compile-time call sites for `logging`). The build computes the closure against the pinned standard library, including the imports inside functions, and fails if it grows beyond the manifest. An optional import (one inside try/except ImportError or with suppress(ImportError)) of a module outside the manifest resolves to ImportError at runtime, as if the module were not installed, and the manifest records each such omission; the closure recorded for v0.3 adds bisect, keyword and reprlib to phase 1 and omits bz2 and lzma for shutil. On 3.15, eleven phase-1 modules bind some imports lazily (PEP 810): `collections`, `contextlib`, `dataclasses`, `typing`, `traceback`, `pathlib`, `argparse`, `inspect`, `difflib`, `tokenize` and `_colorize`. Lazy-import semantics are therefore phase-1 runtime work, and the closure counts a lazy edge as required, because a module that an import-time observation does not show can still be needed at first use. The closure is being recomputed on 3.15.2 (Gate 0). A module not listed is \[P2+\] until the ledger shows it compiles clean; the dependency policy of the design document (section 10.1) decides mapping versus island for third-party packages, not this table.

Import guards (2026-11-01, review log D-3). Only an import inside `try`/`except ImportError` or `with suppress(ImportError)` is optional, and only optional imports are recorded as omissions. The build evaluates a guard that reads nothing but constants, the module's own `__name__` and the target-platform facts the manifest records (`sys.platform`, `os.name`, membership in `sys.builtin_module_names`): an import under a false guard is dead on the target and never compiled, and one under a true guard counts as unguarded. An import under any other guard is required at module level; inside a function it belongs to that function, which the manifest declares unsupported when the import's target is outside the manifest.

The `codeop` shim (2026-11-01, review log D-4). `traceback` imports `codeop`, which E-08 excludes, at module level, and calls `codeop.compile_command` only to suggest a keyword for a `SyntaxError` that carries the parser's private metadata. A compiled program has no parser at runtime (E-01), so it meets such an error only if it builds one and sets that metadata itself. Phase 1 ships a shim for `traceback`'s import: its `PyCF_*` flags have CPython's values, and `compile_command`, `Compile` and `CommandCompiler` stop the program with the E-08 refusal, which no `except` clause catches, because `traceback` makes the call inside `suppress(Exception)` and a catchable error would silently drop CPython's suggestion. A program's own `import codeop` remains a compile-time error.

## 8. Program model

A program is a closed world: the entry module, every module it imports transitively, and the modules named in the dependency policy's registry of computed imports, all resolved at build time. Nothing else can be imported at runtime; `importlib.import_module(name)` with a name outside the registry raises `ModuleNotFoundError` with CPython's message.

Entry and exit. A program starts as `python script.py` or `python -m package` would: `__name__` is `"__main__"` in the entry module, `sys.argv` holds the arguments, `sys.exit` and `SystemExit` set the status, an uncaught exception prints CPython's report to standard error (traceback lines per D-06) and exits with status 1, `atexit` handlers run last in LIFO order.

Name binding. A bare name bound nowhere in its scope chain and not a builtin is a compile-time `NameError`. At runtime a global name resolves to the module global if it is bound at that moment, else to the builtin of the same name if one exists, else raises `NameError`, so a module that assigns and later deletes `len` sees the builtin `len` again, as CPython does. A local that its function binds but has not yet assigned raises `UnboundLocalError`. Builtins may be shadowed by module globals and locals; E-06 excludes rebinding the `builtins` module itself. `globals()[name] = v` and writes through `vars(module)` reach statically known names (section 5). `locals()` inside a function returns a fresh, mutable dictionary each time it is called, and writes to it do not change the function's variables (PEP 667).

Module initialisation. A module is initialised by the first `import` statement that reaches it at runtime, in the importing statement's position, never hoisted and never in a precomputed order; conditional and function-local imports keep their meaning. A lazy import (PEP 810) moves that point to the first use of the name it bound, so the module's effects and its import errors occur there.

&#91;embedded content: module initialisation · absent, initialising, initialised\]

A module entered from a cycle while it is initialising is returned as it stands: names bound so far are readable; `a.x` for a name not yet bound raises `AttributeError`, and `from a import x` raises `ImportError`, each with CPython's "partially initialized module" message. An exception during the body propagates to the importer and the module is removed from `sys.modules`, so a later import runs the body again, as CPython does. A module appears in `sys.modules` when its initialisation starts, whether or not its definitions were staged.

Staging contract. `bella.toml` declares entrypoints run in the host CPython before the snapshot. An entrypoint runs in a sandbox that records every external input it touches (environment variables, files, the clock, randomness, sockets); an undeclared input fails the build, and a declared input is hashed into the artefact key, so a value frozen at build time is a stated build-profile decision. Staging is a compile-time dry run of definition-time code, and it adds nothing observable: it yields the code and layouts to compile (the functions `dataclasses` or `namedtuple` generate, a class's field set, its MRO and descriptors), never objects. At runtime the module body executes in full and in order, including the definition-time expressions of every `def` and `class` (default values, decorators, base expressions, metaclass keywords, class-body statements and hooks), creating ordinary reference-counted function, class and instance objects with their effects intact; the compiled code those objects carry is immortal metadata invisible to the program. A module whose definition-time code reads a recorded input, or is not deterministic, cannot be staged and is compiled from its source without the dry run's help; code it would have generated with `exec` is then not available, and the ledger reports it as a candidate for the island or for rewriting.

Environment. `PYTHONHASHSEED` is honoured (D-14); UTF-8 mode is always on and cannot be turned off (D-15; CPython 3.15 turns it on by default, PEP 686); `PYTHONPATH`, `.pth` and `.start` files (PEP 829) and `site` customisation are ignored (E-04), and so are `PYTHON_LAZY_IMPORTS` and `-X lazy_imports`: the lazy-imports mode is always `normal` (D-18); `sys.path` is readable and reflects the build. The supported `sys` surface is `argv`, `exit`, `stdin`/`stdout`/`stderr`, `path` (read), `platform`, `version`, `version_info`, `implementation` (D-16), `flags`, `maxsize`, `float_info`, `int_info`, `getrecursionlimit`/`setrecursionlimit` (D-17), `exc_info`, `exception`, `intern`, `getsizeof` (unobservable value), `set_int_max_str_digits`; everything else is \[P2+\] or \[X\].

Resources. Allocation failure raises `MemoryError` where the runtime can detect it; recursion is bounded by a per-call depth counter that raises RecursionError at sys.getrecursionlimit(), default 1000 (decision 2, D-17); the main thread's stack is 8 MiB and other threads' 2 MiB unless the policy file says otherwise (decision 16). The first release targets Linux on x86-64 and aarch64 (decision 14).

## 9. Finalisation and resources

Reference counting is part of the dialect's semantics, not an implementation choice: a program may rely on an object being finalised when its last reference goes away, exactly as it may under CPython.

- Dropping the last reference to an object not on a cycle finalises it immediately and synchronously, before the dropping statement completes; the cascade into its referents is synchronous too.
- For such an object the sequence is CPython's refcount path: `__del__` runs first, once per object (PEP 442); if it resurrects the object, disposal stops and the object lives on with its weak references intact; otherwise weak references are cleared and their callbacks run, then memory is released. An exception from `__del__` is printed to standard error and ignored.
- Objects on a reference cycle are finalised by the collector at an unspecified later time (D-04), with PEP 442's cyclic sequence, which differs from the refcount path: first the weak references that have callbacks are cleared and their callbacks run; then the finalisers of every member run, in an unspecified order, and a weak reference without a callback still resolves inside them; then the group is checked for resurrection: a resurrected group lives on, and its callback-less weak references with it; otherwise the remaining weak references are cleared and the members are cleared and released. This is CPython 3.15's sequence (C-9-02, C-9-07); 3.14 cleared every weak reference first. `gc.collect()` forces a complete collection synchronously and returns the number of unreachable objects found; `gc.disable` and `gc.enable` are honoured; `gc.freeze` and the introspection functions are \[X\] (E-05).
- A generator whose last reference is dropped while suspended is closed: `GeneratorExit` is raised at the suspension point, `finally` blocks and `__exit__` methods run, and a generator that yields during close raises `RuntimeError`, as CPython does.
- A file object finalised while open is closed, with a `ResourceWarning` under the same conditions as CPython.
- `with` is the only guaranteed resource discipline for cyclic or shared objects, because finaliser timing for those is unobservable.
- At exit, `atexit` handlers run in LIFO order, then module globals are finalised in an unspecified order (D-07); daemon threads are \[P2+\].
- Module objects are immortal (D-19). Functions, classes and every other object created while a module initialises are reference-counted like any other, so `del f` releases a function's defaults and closure exactly when CPython would.

## 10. Conformance

This document is the test plan: every normative sentence maps to at least one conformance clause, and a release claims a scope marker only for the clauses it passes.

The corpus. Clauses are numbered `C-<section>-<n>` and each one is a test function that runs unchanged under CPython 3.15 and under the compiled program. Sources: tests adapted from CPython's `Lib/test` (`test_grammar`, `test_class`, `test_descr`, `test_int`, `test_float`, `test_dict`, `test_set`, `test_generators`, `test_exceptions`, `test_with`, `test_import` and relatives; PSF-licensed, never shipped), tests written for the clauses CPython's suite does not isolate, and the three target programs of the design document's phase 0.

The harness compares the first table of section 2 and nothing else: standard output and standard error with traceback lines normalised per D-06 and the runtime-generated wording of built-in exception messages masked per exception type (D-08), exit status, the class and structured payload of every exception at the point it is raised, the mutation trace recorded by instrumented test fixtures, and the effect log of the sandbox. A difference is a defect unless the deviation register names it.

Generated programs. Hypothesis with a grammar-based source generator (hypothesmith or an in-house one) produces well-formed programs for each IR level; the differential runner shrinks a failing program to a minimal reproducer and files it as a new clause. The corpus therefore grows from failures, which is the intended direction.

Passing. A phase-1 release MUST pass every \[P1\] clause on the corpus and show no unregistered divergence on the generated programs over a fixed budget of runs; a \[P2+\] clause MUST fail with the milestone-naming error, never pass by accident.

Deviations. A difference inside the first table that the project chooses to keep gets a register entry with an id, the constructs affected, the rationale, whether `bella-lint` can detect dependence on it, and the phase in which it expires if it is temporary. No deviation ships undocumented; the register is the only place a compiled program is allowed to differ.

## 11. Deviation register

| Id | Deviation from CPython 3.15 | Status | Detectable by lint |
| --- | --- | --- | --- |
| D-01 | `id()` returns a runtime address that differs from CPython's and may be reused differently | Accepted (decision 1) | Yes: any `id(` call |
| D-02 | Default `__repr__` prints a different address after `at 0x` | Accepted (decision 1) | Yes: `repr` of an object without `__repr__` in output |
| D-03 | `is` is true between equal small-integer immediates and between equal interned strings more often than in CPython | Accepted (decision 1; code that depends on it is wrong by the dialect's standards) | Yes: `is` with a literal operand |
| D-04 | Reference cycles are collected at a different moment and their members are finalised in a different order | Accepted | Partial: classes with `__del__` that can form cycles |
| D-05 | `set` and `frozenset` iteration order for elements hashed by value (`int`, `str`, `bytes`, tuples of these); for identity-hashed elements the order is unobservable in CPython as well, so no rule applies | Decided (decision 4): CPython's set table algorithm, so order matches for value-hashed elements | Yes: iteration over a set reaching output |
| D-06 | Traceback line text in uncaught-exception reports and `traceback` formatting | Decided (decision 6): release builds print file and line only; debug builds reproduce CPython's format from source maps | Yes: `traceback` module use |
| D-07 | Finalisation order of module globals at exit | Accepted (unspecified in CPython) | No |
| D-08 | Runtime-generated human-readable wording of built-in exception messages ("list index out of range", "unsupported operand type(s)"); structured and user-supplied payloads are not covered and must match (section 2) | Decided (decision 11): wording free for now; a program that prints or branches on the exempt wording (`str(exc)` or `exc.args[0]` of a built-in exception the runtime raised) is outside the guarantee, and `bella-lint` flags such uses where it can see the exception's type; the harness masks the wording per exception type; revisit at phase 2 | No |
| D-09 | `assert` is always active; `-O` and `-OO` do not exist | Decided (decision 7): assertions active by default; a build-profile switch that strips them and makes `__debug__` false is planned \[P2+\] | Yes: `__debug__` reads |
| D-10 | `return`, `break` or `continue` leaving `finally` is a compile-time error (CPython warns) | Decided (decision 8): compile-time error | Yes |
| D-11 | `breakpoint()` prints a warning and continues | Decided (decision 9): warning and continue | Yes |
| D-12 | `__file__` is the source path recorded at build, not a path on the running machine | Accepted | Yes: `__file__` reads |
| D-13 | `str` internal representation (no observable difference intended; listed because indexing cost differs) | Decided (decision 3): PEP 393 representation (Latin-1, UCS-2 or UCS-4 per string, O(1) indexing) with a UTF-8 copy cached on demand; no observable difference | No |
| D-14 | Hash randomisation uses SipHash-1-3 with the `PYTHONHASHSEED` protocol; a program that fixes the seed sees CPython's values only if the runtime's seeding matches CPython's | Accepted (decision 5: randomisation on); seeding compatibility with CPython is a conformance clause | No |
| D-15 | UTF-8 mode is always on and cannot be turned off (`PYTHONUTF8=0`, `-X utf8=0`); `PYTHONIOENCODING` and `encoding="locale"` are ignored and mean UTF-8. Narrowed in v0.4: CPython 3.15 turns UTF-8 mode on by default (PEP 686), so every other encoding default agrees | Decided (decision 10): UTF-8 mode always on | Yes: `encoding="locale"` |
| D-16 | `sys.implementation.name` and `platform.python_implementation()` name the converter, not CPython | Decided (decision 12): `sys.implementation.name == "bella"`, `platform.python_implementation() == "Bella"` | Yes |
| D-17 | Recursion limit behaviour | Decided (decision 2): a per-call depth counter raises `RecursionError` at `sys.getrecursionlimit()`, default 1000; cost measured in phase 2 | Yes: `setrecursionlimit` |
| D-18 | `PYTHONPATH`, `.pth` and `.start` files, `site`, and the lazy-imports mode (`PYTHON_LAZY_IMPORTS`, `-X lazy_imports`; always `normal`) are ignored; `sys.path` reflects the build | Accepted (closed world) | Yes |

Added after review round two and narrowed after round three: D-19, module objects are immortal (a module can leave `sys.modules` only through E-04, which is excluded). Functions, classes and every other definition-time object are reference-counted like any other, so `del f` releases a function's defaults and closure when CPython would; compiled code and class layouts are immortal metadata the program cannot observe. Accepted; nothing to detect.

## 12. Pending decisions

Decided on 2026-10-30; the fourth column is authoritative, and the register and the sections now reflect it. Two decisions departed from the recommendation: built-in exception message text is free for now (D-08), and assertions get a planned build-profile switch that strips them from compiled output (D-09). The project is named Bella and licensed MIT (decision 17); `sys.implementation.name` is `"bella"` (decision 12); tool and file names follow the name: `bella.toml`, `bella-lint`, `bella-plugin-<name>`.

| # | Decision | Options | Recommendation | Marcin decision |
| --- | --- | --- | --- | --- |
| 1 | Addresses and identity (D-01, D-02, D-03) | Accept the deviations, or emulate CPython's small-int cache and interning rules for `is` | Accept; CPython itself warns on code that depends on these | accepting; code depending on that is wrong by our standards |
| 2 | Recursion limit (D-17) | (a) a per-call depth counter raising `RecursionError` at `sys.getrecursionlimit()` (a few cycles per call); (b) guard pages, free, but a stack overflow aborts with a message instead of raising | (a), always on; measure the cost in phase 2 and revisit only if it shows | (a) |
| 3 | `str` representation (D-13) | (a) PEP 393 Latin-1/UCS-2/UCS-4 with O(1) indexing, UTF-8 copy cached on demand; (b) UTF-8 with a lazy code-point index, zero-copy for C libraries, O(n) first index on non-ASCII text | (a) for the first release: exact parity with CPython's cost model and simpler proofs; FFI copies are cheaper than surprising indexing cost | (a) |
| 4 | Set iteration order (D-05) | (a) implement CPython's set table algorithm so order matches given equal hashes; (b) declare unobservable | (a); programs print sets, and the cost is one data structure | (a) |
| 5 | Hash randomisation (D-14) | On with the `PYTHONHASHSEED` protocol, or off (deterministic hashes) | On; hash-flooding is a real denial-of-service vector | On |
| 6 | Traceback text (D-06) | (a) reproduce CPython's format from source maps in every build; (b) file and line only in release builds, full format in debug builds | (b) | (b) |
| 7 | Assertions (D-09) | Always on, or honour a `-O` equivalent in the policy file | Always on | On; to be disabled in compiled resulting code eventually |
| 8 | Control flow leaving `finally` (D-10) | Compile-time error, or CPython's warning | Error; 3.14 already warns and later versions will reject | Error |
| 9 | `breakpoint()` (D-11) | Warning and continue, or compile-time error | Warning and continue, so a forgotten call does not fail a build | warning |
| 10 | Encodings (D-15) | UTF-8 mode always, or honour locale and `PYTHONIOENCODING` | UTF-8 always; CPython is moving there (PEP 686) | UTF8 |
| 11 | Exception message text (D-08) | Identical to CPython 3.14, or free | Identical; programs match on messages | free for now |
| 12 | Implementation identity (D-16) | `sys.implementation.name` names the converter, or claims `cpython` | Name the converter; libraries that branch on the name are rare and should see the truth | names "Bella" |
| 13 | Shared-container memory model (applies at \[P2+\]) | Per-operation atomicity for `list`, `dict`, `set` as in free-threaded CPython, or stronger | Per-operation atomicity, nothing more | per-op |
| 14 | Platforms for the first release | Linux x86-64 and aarch64 only, or add macOS or Windows with GCC | Linux only | 1) linux on x64 and arm only |
| 15 | Grammar freeze | 3.14 for phases 0 to 2, or track the newest CPython | 3.14 frozen; PEP 649 annotations and t-strings included | 3.15, revised on 2026-11-01 from 3.14: the newest stable release, since there is no legacy to keep |
| 16 | Thread and main-thread stack sizes | 8 MiB main, 2 MiB threads (platform defaults), or larger | Defaults, overridable in the policy file | defaults |
| 17 | Project name and licence | A real name (PyPI and GitHub availability), MIT for the compiler and runtime | Decide before phase 0 publishes anything | "Bella"; MIT |

## 13. Revision log

v0.1 (2026-10-30, after review round two): reference build pinned to CPython 3.14.8 (section 1); address-derived values compared up to a consistent renaming and identity-derived hashes exempted in value (section 2); builtins fall-through for unbound globals, `locals()` as a fresh mutable dictionary, `__dict__` presence by the MRO rule, and the `site` builtins named (section 3); phase-1 library set turned into a dependency-closed manifest with the `threading` shim, single-threaded `contextvars`, `copyreg`, `gettext` and the `locale` subset, `traceback` formatting and compile-time call sites for `logging` (section 7); partially initialised modules raise `AttributeError` on attribute access and `ImportError` on from-import, and `sys.modules` visibility fixed at initialisation start (section 8); staging split into frozen definitions and runtime effect statements (section 8); PEP 442's cyclic sequence and resurrection (section 9); D-05 qualified and D-19 added (section 11).

v0.2 (2026-10-30, decisions taken): recursion counter (D-17); PEP 393 strings (D-13); CPython's set algorithm for value-hashed elements (D-05); hash randomisation on (D-14); file-and-line tracebacks in release builds (D-06); assertions on by default with a planned build-profile switch (D-09); control flow out of `finally` is an error (D-10); `breakpoint()` warns (D-11); UTF-8 mode always (D-15); built-in exception message text free for now, with the harness comparing class and position instead (D-08); implementation name `bella` (D-16); per-operation atomicity for shared containers; Linux x86-64 and aarch64; grammar frozen at 3.14; default stack sizes; project name Bella, MIT.

v0.3 (2026-10-30, after review round three): PEP 442's cyclic sequence corrected to weak references first, then finalisers, then the resurrection check (section 9); staging restated as a compile-time dry run that yields code and layouts only, with every definition-time expression executed at runtime and D-19 narrowed to module objects (sections 8, 9, 11); instance dictionaries given an independent lifetime, sharing and replacement, and the `__dict__` presence rule restated as inherited layout capability (section 3); the `threading` shim reconciled with section 3; `bisect`, `keyword` and `reprlib` added to phase 1 and the optional-import policy stated (section 7); D-08 narrowed to runtime-generated wording with structured payloads kept observable, and the harness rule updated (sections 2, 10, 11).

v0.4 (2026-11-01, reference moved to CPython 3.15.2): the pin moves from 3.14.8 to 3.15.2, the newest stable release, and the grammar freeze to 3.15 (sections 1 and 3, decision 15). PEP 810 lazy imports are \[P1\] because eleven phase-1 modules use them, and a lazily imported module is initialised at the first use of its name (sections 3, 7, 8); PEP 798 unpacking in comprehensions is \[P2+\] (section 3); `frozendict` and `sentinel` get commitments (sections 3, 6); `profiling` joins E-03 and `sys.set_lazy_imports` joins E-04 (section 4). The cyclic finalisation sequence follows 3.15: weak references without callbacks stay alive inside the finalisers and through a resurrection (section 9; C-9-02, C-9-07). D-15 narrows, since 3.15 turns UTF-8 mode on by default, and D-18 adds `.start` files and the lazy-imports mode (section 11). The corpus was re-recorded on 3.15.2, and two observables changed, both new in 3.15 (C-3-06, C-9-02).

v0.5 (2026-11-01, review log D-3 and D-4): only imports under `try`/`except ImportError` or `suppress(ImportError)` are optional; guards over constants, `__name__` and the recorded platform facts are evaluated at build time, an import under a false guard is dead, and an import under any other guard is required at module level and belongs to its function inside a function (section 7). `traceback` imports a `codeop` shim whose compiling functions stop the program with the E-08 refusal; E-08 itself is unchanged (sections 4 and 7).
