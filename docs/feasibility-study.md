# Python → C++26 by intent-level AST passes: feasibility study

Oct 28, 2026 · @Marcin Gałczyński

## 1. Verdict

Feasible as a closed-world compiler for a written-down Python dialect; not feasible as a transparent replacement for CPython. Every construct the passes can prove something about (type, ownership, thread-locality, fixed class layout) lowers to native C++. Everything they cannot prove lowers to calls into a small runtime object model, which is slower.

The project's quality is decided by how much the passes prove, not by the choice of C++ as the target. Translating syntax one-to-one gives Nuitka-class results (1.5-3x); translating intent after type and ownership recovery gives Codon-class results (10-100x on typed code). The architecture below is built so that the proof-carrying passes, not the printer, do the work.

Three decisions define the project:

1. A dialect, written down. Only `eval`, `exec` and `compile` of source strings, and frame or bytecode introspection, are rejected at compile time; every other dynamic feature (`__getattr__`, class mutation, runtime-created classes, computed attribute names) is admitted as a tier with a stated cost (design document, section 7). The dialect states which semantics are kept exactly (arbitrary-precision `int`, insertion-ordered `dict`, floor division, exception types, destructor timing on refcount drop).
2. A staged pipeline of IRs, each lower than the last, where every pass records what it proved. The C++ output is a pretty-print of the last IR, never a rewrite of Python syntax.
3. A per-package linking policy. Pure-Python packages compile through the same pipeline into binaries plus a typed interface file. C-extension packages get either an intent mapping onto a C++ library or an embedded free-threaded CPython island behind a bridge.

What each goal costs:

- Source visibility: no longer a requirement; an optimised native binary is already impractical to reverse into Python, so the generated C++ is kept readable instead (section 10).
- Speed: depends on type and ownership recovery; expect 10-100x on typed numeric code, 1.5-3x on object-heavy dynamic code, about 1x on I/O-bound code (section 11).
- No global stop in steady state: compile-time ownership elision, biased reference counting and a concurrent cycle collector, with a bounded all-thread handshake left under memory pressure; this is the hardest runtime component, it arrives in phase 4 after a synchronous collector has shipped, and it is the one CPython itself just retreated on (section 6).
- GIL removal: the interpreter's reasons for a GIL vanish in compiled code; what remains is the C-extension ecosystem, which is a linking problem, not a language problem (sections 7 and 8); the threaded runtime itself is a phase-4 milestone, and the first release is single-threaded.
- Licensing: the pipeline can be built entirely from MIT/BSD parts except the C++ compiler itself (Clang is Apache-2.0 with LLVM exception, GCC is GPL with runtime exception); both are tools run as processes, not linked libraries, so the output is unencumbered (section 12).

Status: historical. This study is the record of the initial analysis (2026-10-28) and is kept unchanged below except for marked corrections. The [design document](https://claude.ai/artifact/85e8947GSEJ2bgafhvrDYr) and the [dialect specification](https://claude.ai/artifact/AAhUTkzPziD9NH5PsscHwN) are authoritative, and several mechanisms described here have been superseded there: dependency-order module initialisation (replaced by initialisation at the first import statement), the projection sort for `sorted(key=)` (a stable sort over cached keys), deferred reference counting (dropped), the C++23 fallback profile (GCC 16 at C++26 only), the global side table (a per-instance dictionary slot), the stable-ABI bridge (version-specific), and the phase order (coverage before speed, with the synchronous collector in phase 1).

## 2. The layered IR

&#91;embedded content: IR pipeline · 8 stages, 2 side inputs, 1 runtime library\]

Proofs travel downward only: the printer reads nothing but the C++ intent IR, the staging pass turns definition-time metaprogramming into snapshotted objects before desugaring, and the type oracle is what turns a desugared tree into typed IR.

Each level is a separate schema with its own invariants, so a pass can be unit-tested against inputs at its level without running the whole pipeline. The two lowest levels are where the project differs from every transpiler before it: the ownership IR records who owns what and which thread may touch it, and the C++ intent IR is a C++ program in tree form, type-checked by the compiler before a line of text exists.

## 3. Pass pipeline

Each pass consumes one IR level, proves one kind of fact, and either lowers a construct or records the fact for later passes; no pass emits C++ text, and every pass carries a specification and a proof obligation (design document, sections 8 and 9). The order is the dependency order, and a pass that fails to prove something leaves the construct boxed rather than guessing.

1. Parse to a lossless tree (positions, comments, tokens kept) for diagnostics and source maps. CPython's own `ast` plus token offsets is enough; libcst (MIT) when exact round-tripping is wanted.
2. Symbol table: scopes, cells for `nonlocal`, globals, `__slots__`, class bodies. Decides which locals become C++ locals and which become shared cells.
3. Import graph and module ordering: `import`, `from x import y` and star-imports resolved statically. Module-level code becomes one `init()` per module run in dependency order, which removes C++'s static-initialisation-order problem. Computed-name imports resolve at runtime against the registry of compiled modules; a module outside the closed world raises `ModuleNotFoundError`.
4. Compile-time staging: module-level and class-body code that is pure is executed once in the compiler's host CPython. The resulting classes, enums, dataclasses, namedtuples and constants are snapshotted and lowered from the result, not from the code that built them. This neutralises the `exec`-based idioms in `dataclasses`, `collections.namedtuple`, `enum` metaclasses and `typing` without emulating them at runtime; RPython and Nuitka both rely on this trick.
5. Desugaring to PyCore: comprehensions become scoped loops; `with` becomes try/finally over `__enter__`/`__exit__`; decorators become calls; f-strings become format calls; chained comparisons become `and`-chains; `match` becomes a decision tree; `for` becomes the iterator protocol; augmented assignment becomes `__iadd__` with fallback; default arguments are evaluated once at definition time.
6. Type oracle: mypy (MIT) run as a library, or pyrefly or ty (both MIT), over the whole program with stub interfaces for compiled dependencies; the type of every expression is harvested. Annotations are required at package boundaries and inferred inside. Optionally, types observed under `sys.monitoring` during the test run are added as speculation with guards.
7. Typed IR construction: ANF/SSA form; every operation named by protocol (`GetItem`, `Truth`, `Iter`, `Next`, `BinOp(Add)`); the boxed `Object` type appears only where the oracle returned `Any` or an unresolvable union.
8. Closed-world class analysis: hierarchy, final classes, C3 linearisation, layout freezing (every literal attribute name ever assigned to instances of a class becomes a field), per-slot write detection (a method assigned anywhere makes that slot writable and its calls indirect), devirtualisation of everything else. `__getattr__` is bound directly on literal-name misses; `__getattribute__` and `__setattr__` turn every access on that class into a call; computed names go through the field table and the side table (design document, sections 3 and 7).
9. Integer range and bounds analysis: `range(len(xs))` loops, slice indices and arithmetic that provably stays within 63 bits become machine integers; everything else keeps the tagged small-int/bigint representation with overflow promotion.
10. Protocol resolution: `len(x)` becomes `.size()` on frozen classes; `in` becomes `contains`; truthiness becomes a direct test; `str.join`/`split`/`format` become ranges views and `std::format`; `sorted(key=)` becomes `ranges::sort` with a projection; `d[k]` under `except KeyError` becomes `find`.
11. Exception lowering: locally handled exceptions become `std::expected` or plain branches (`StopIteration`, `KeyError`, `ValueError` from parsing); the rest become C++ exceptions in a `PyError` hierarchy; `finally` becomes an RAII guard.
12. Escape and alias analysis, then ownership annotation: value on the stack; unique (`std::unique_ptr` or C++26 `std::indirect`); shared thread-local (non-atomic count); shared cross-thread (biased count); immortal (constants, module globals, interned strings). Containers whose elements unbox become `std::vector<T>` of values.
13. Cycle-freedom classification: from the frozen class graph, types that can never sit on a reference cycle are marked; their instances carry no cycle-collector header (a `list[int]` cannot be cyclic, a `Node` with `next: Node | None` can).
14. Thread-locality: objects proven never to leave their creating thread get no per-object lock and non-atomic counts.
15. Arena assignment: allocations proven to die before the enclosing function returns are bump-allocated in a per-thread arena released at return.
16. Generator and async lowering: generator functions become `std::generator<T>` (C++23), or a custom coroutine type when `send`/`throw`/return values are used; `async def` becomes a C++20 coroutine scheduled through `std::execution` (C++26), `await` becomes `co_await`, `gather` becomes `when_all`.
17. C++ intent IR: a C++-semantic tree of modules, structs, templates, concepts, ranges pipelines, coroutines and variants, checked for well-formedness (types resolved, no dangling references) before printing.
18. Emit: one C++ module unit per Python module (`export module pkg.mod;`), one static library per package, one typed interface file per package, one build file; compiled with GCC or Clang at `-std=c++26` with a C++23 fallback profile; LTO at final link gives cross-package devirtualisation.
19. Differential check: the project's own tests run under CPython and under the binary; any divergence is a compiler bug or a dialect violation, never a silent acceptance.

## 4. Semantic gap, construct by construct

The rule for every row: keep the semantics that programs observe, lower the mechanics. "Express intent" means the IR carries `Iterate(xs)` or `Truth(x)`, not CPython's `PyObject_GetIter` call sequence; it does not license changing what a program computes.

| Construct | Python semantics that programs observe | Intent lowering when proven | Residue and dialect rule |
| --- | --- | --- | --- |
| `int` | Arbitrary precision; `bool` is an `int`; `//` and `%` floor toward minus infinity; `**` exact | 63-bit tagged small int with overflow promotion to a heap bigint; plain `int64_t`/`size_t` when range analysis proves bounds; floor-div and mod helpers inlined | Exact semantics always; never 64-bit truncation (Codon's 64-bit `int` is the deviation to avoid); full specification in the design document, section 6 |
| `float` | IEEE double; shortest round-trip `repr`; `round()` half-to-even; zero division raises | `double`; `std::to_chars` for repr; division check only when the divisor is not proven nonzero | None |
| `str` | Immutable Unicode code points; rich methods; cached hash; interning | Runtime `Str`: UTF-8 bytes, cached hash, ASCII flag, lazy code-point index; methods map to `views::split`, `views::join_with`, `contains`, `std::format` | `std::string` is never the Python `str`; O(1) code-point indexing only on the ASCII path |
| `list` | Reference semantics and aliasing; negative index; slicing copies; `IndexError` | `std::vector<T>` by value when escape analysis proves one owner; shared handle otherwise; bounds checks dropped when range analysis proves them; read-only non-escaping slices become `std::span` | Heterogeneous lists become `vector<Object>` |
| `dict` | Insertion order; `__hash__`/`__eq__` protocol; mutation during iteration raises | Compact ordered map (index array plus entry vector, CPython's own layout) in the runtime; constant-key dicts become structs (shape inference); `std::flat_map` only for small static maps | `std::unordered_map` is never a Python dict (no order) |
| `tuple`, `set` | Value tuples; hashable elements | `std::tuple` when arity is static; `std::inplace_vector` (C++26) for small variable arity; `ankerl::unordered_dense::set` (MIT) for sets | Unhashable-element errors move to compile time where types are known |
| Truthiness, `and`/`or` | Return operands, not bools; `__bool__` then `__len__` | `Truth(x)` resolved per type; `a or b` becomes a conditional over `std::common_type`, else boxed | None |
| Attribute access | `__dict__`; class mutation; descriptors; `__getattr__` | Frozen layouts become struct fields; literal attribute names assigned anywhere in the program join the layout; properties become accessors; descriptors resolve statically | `__getattr__` is called directly on literal-name misses; computed names go through the class field table (offset per name) and a side table; nothing here is a dialect error (design document, section 7) |
| Inheritance, MRO | C3 linearisation; `super()`; stateful multiple inheritance; metaclasses | Single inheritance becomes C++ inheritance; sealed hierarchies become `std::variant` dispatch or switch on class id; stateless mixins become deducing-this (C++23) mixins | Stateful multiple inheritance becomes generated MRO-ordered method tables (slower); metaclasses run at compile time when stageable, otherwise the class is built at runtime in dict mode (slower, still admitted) |
| Functions | Closures; defaults; `*args`/`**kwargs`; keyword-only; first-class values | Lambdas capturing by value; `nonlocal` cells shared; known call sites specialised per arity with designated-initialiser argument structs; function values as `std::function_ref` (C++26) or `std::copyable_function` | Unknown-callee `**kwargs` becomes a runtime keyword map |
| Decorators | Arbitrary wrapping at definition time | `property`, `staticmethod`, `classmethod`, `dataclass`, `cache`, `contextmanager` applied at compile time; other pure decorators staged | Decorators depending on runtime state become `copyable_function` wrappers |
| Exceptions | Control-flow use; hierarchy; `finally`; tracebacks | Locally handled become `std::expected` or branches; unhandled become C++ exceptions in a `PyError` hierarchy; `finally` becomes an RAII guard; `std::stacktrace` opt-in | Tracebacks lose line numbers unless debug info is kept |
| Generators | `yield`, `yield from`, `send`, `throw`, return value | `std::generator<T>` (C++23); custom coroutine promise when `send`/`throw`/return value are used | None |
| `async`/`await` | Event loop; tasks; cancellation; `gather` | C++20 coroutines on `std::execution` schedulers and `execution::task` (C++26); loop on libuv (MIT) | asyncio's API surface is a library port, not a language lowering |
| `with` | `__enter__`/`__exit__`; exception suppression | RAII guard whose destructor receives the exception pointer | None |
| `match` | Structural, class and literal patterns; guards | Decision tree over `std::variant`, `std::visit` and `if` chains; C++26 has no native pattern matching | None |
| Imports, module globals | Executed at import; `sys.path`; reload | Static graph; one `init()` per module; globals as immortal objects | Computed-name imports resolve against the registry of compiled modules; a module outside the closed world raises `ModuleNotFoundError` |
| `eval`, `exec`, `inspect`, frames, `locals()` | Full reflection over live code | No lowering | The only dialect error; an embedded-CPython island is the escape hatch for a package that needs it |
| `__del__`, finalisation | Runs when the refcount drops; cycles collected later | Deterministic destruction kept by reference counting; cycles finalised by the collector | Objects proven cycle-free keep exact CPython timing; cyclic ones get collector timing |
| `pickle`, `deepcopy`, `__reduce__` | Reflection over object state | Generated per frozen class, from the compiler's own layout knowledge or C++26 reflection in the runtime | Dynamic classes go through the runtime object model |

## 5. Type recovery

Types are the single input that decides whether a line compiles to native C++ or to boxed calls, so the pipeline should take types from four sources and merge them, rather than inventing its own inference. Whole-program inference on its own (Shed Skin's iterative analysis, Agesen's cartesian-product algorithm) is exponential in the worst case and stops scaling around tens of thousands of lines; it is a fallback, not the design.

| Source | What it gives | Limits | Role in the pipeline |
| --- | --- | --- | --- |
| Annotations (PEP 484/604/695 syntax) | Precise types at function and class boundaries | Only where authors wrote them; `Any` is common | Required at package boundaries; the dialect can mandate them for exported APIs |
| Oracle type checker run as a library: mypy (MIT), pyrefly (MIT), ty (MIT) | A type for every expression, narrowing inside branches, generics, protocols; the same machinery mypyc builds on | Unions and `Any` where the checker gives up; stubs needed for compiled dependencies | Primary source; one run per build, results attached to the typed IR |
| Local flow inference inside the compiler | Literal types, loop-variable ranges, container element types from construction sites, `isinstance` guards | Intraprocedural | Refines oracle results and feeds the range and bounds pass |
| Profile-guided speculation | Types observed under `sys.monitoring` (PEP 669) while the test suite runs | Unsound; needs guards and a boxed fallback path | Optional tier for hot paths; turns `Any` into a guarded fast path with a slow path behind it |

Two design points follow. First, the `Object` box must be a real, well-optimised type, not an afterthought: tagged pointers, inline caches at call sites and hidden-class attribute lookup, because every real program keeps some dynamic residue. Second, the type oracle's output format should be stored in the package interface file (section 8), so a compiled library's exported types feed the oracle of the next package without re-analysing the source.

Generic code (`def first(xs: list[T]) -> T`) becomes a C++ template instantiated at the call site. That forces generic bodies into the C++ module interface rather than the static library, exactly as Swift ships generic bodies in its module interface; monomorphisation across package boundaries is then paid at the final build, not at library build.

## 6. Memory management without a global stop

The recommendation is a five-tier scheme: compile-time ownership first, reference counting for what is shared, and a concurrent cycle collector only for the types that can form cycles. A tracing collector as the primary mechanism is the wrong fit here: it costs Python's deterministic `__del__` and file-closing semantics, it needs precise roots that C++ compilers will not emit, and every production-grade concurrent tracer still has short atomic pauses.

| Approach | Pause behaviour | Runtime cost | Fit with Python semantics | Licence path |
| --- | --- | --- | --- | --- |
| Tier 0: static ownership from escape analysis (stack values, `std::unique_ptr`, C++26 `std::indirect`/`std::polymorphic`) | None | None | Exact, for objects proven unshared; most locals, temporaries and loop state | Compiler's own work |
| Tier 1: per-thread arenas for allocations proven to die at function return | None | Near zero (bump pointer) | Exact | Own code over mimalloc (MIT) |
| Tier 2: non-atomic reference counting for thread-local shared objects | None; frees are deterministic | Low | Exact `__del__` timing | Own code |
| Tier 3: biased reference counting (owner thread non-atomic, others atomic) plus immortal objects and deferred counting for stack-heavy references | None | Moderate; this is the free-threaded CPython recipe (PEP 703) | Exact for most objects | Own code |
| Tier 4: concurrent trial-deletion cycle collector (Bacon and Rajan, 2001) over candidate roots only | No global stop; per-thread epoch handshakes | Paid only by cycle-capable types | Cycles finalised late, as in CPython | Own code |
| Alternative: cppgc/Oilpan from V8 | Incremental and concurrent mark and sweep, one short atomic finalisation pause per heap; heaps are thread-local by design | Write barriers, `Member<T>` handles, generated `Trace()` methods | Loses deterministic finalisation; cross-thread references need special roots | BSD-3 ([cppgc README](https://chromium.googlesource.com/v8/v8.git/+/HEAD/include/cppgc/README.md)) |
| Alternative: MMTk with the LXR plan (counting plus Immix plus concurrent tracing for cycles) | Short pauses; limited stop-the-world copying to defragment | Rust core, a VM binding to write | Conceptually the closest tracing design to the recommendation | Apache-2.0 or MIT, user's choice ([mmtk-core](https://github.com/mmtk/mmtk-core)) |
| Alternative: Boehm conservative collector (what Codon uses) | Mostly stop-the-world; incremental mode via page protection | Conservative scanning everywhere | Loses `__del__` timing; finaliser order undefined | Permissive, MIT-like |

Why counting plus trial deletion avoids the global stop. A trial-deletion collector never scans stacks: its roots are objects whose count was decremented to a nonzero value, recorded in a per-thread buffer. It marks, scans and collects from those candidates while mutators run, using an epoch (the C++26 `std::rcu_domain` or `std::hazard_pointer` machinery, or xenium (MIT) until standard libraries ship them) to know when a retired object is safe to free. The only cross-thread coordination is a ragged handshake where each thread publishes its buffer at its next safe point; no thread waits for another.

The compiler shrinks the collector's job before it runs. The cycle-freedom pass (section 3, pass 13) removes whole classes from tracking: a `list[int]`, a `str`, a dataclass of scalars, a `dict[str, float]` can never be on a cycle, so they carry no collector header and are freed by their count alone. What remains is graph-shaped user data, caches with back-references and closures capturing their owner; those get a 16-byte header and the write-barrier-free trial deletion.

Three hazards and their mitigations:

- Cascading frees. Dropping the last reference to a large structure frees millions of objects synchronously. Mitigation: a per-thread deferred-free queue drained in bounded slices, with a memory-pressure governor that drains faster when the allocator reports growth.
- Memory growth under a lazy collector. CPython shipped an incremental collector in 3.14.0 and [reverted it in 3.14.5 (May 2026)](https://www.python.org/downloads/release/python-3145/) after reports of significant memory pressure in production. The lesson: pause targets must be paired with a growth bound, so the collector escalates to a synchronous local pass when a thread's cycle-candidate heap exceeds its limit; that pass is still per-thread, never global.
- Roots in C++. Optimising compilers keep derived pointers in registers and drop the base, so precise stack maps are unavailable. The counting design sidesteps this entirely; if a tracing tier is ever added (for example cppgc for a specific subsystem), it must scan stacks conservatively and the heap precisely, the way Oilpan and JavaScriptCore do.

Allocator. mimalloc (MIT) gives per-thread heaps, no global lock, and heap-walking support the collector can use to enumerate candidates; it is also what free-threaded CPython chose, so its behaviour under Python-like allocation patterns is well understood.

## 7. GIL eradication

The GIL is not a language feature; it is an implementation lock protecting five things inside CPython, and a compiled program has to replace each one separately. Free-threaded CPython, [officially supported since 3.14 (PEP 779)](https://www.python.org/downloads/release/python-3145/), has already done this work for an interpreter, and its choices are the reference for a runtime that starts with far more static knowledge.

| What the GIL protected | Replacement in the compiled runtime | Cost when it applies |
| --- | --- | --- |
| Refcount atomicity | Compile-time elision (tiers 0-1), non-atomic counts for thread-local objects (tier 2), biased counts, immortal and deferred counting for the rest (tier 3) | Near zero for proven-local objects; one atomic per cross-thread touch otherwise |
| Interpreter data structures (code objects, frames, type caches) | None exist; the runtime's own global tables (interned strings, hidden-class transitions, module globals, type registry) are read lock-free under `std::hazard_pointer` or `std::rcu_domain` (C++26) and resized without stopping readers | Readers free; writers copy-on-write |
| Crash-safety of `list`/`dict`/`set` under unsynchronised sharing | Per-object lightweight lock on mutation plus optimistic lock-free reads (the free-threaded CPython critical-section design); elided entirely when the thread-locality pass proves the object never escapes its thread | Uncontended lock on mutation of shared containers only |
| C extensions written for the GIL | Isolated inside the embedded CPython island (section 8); on a free-threaded 3.14t build, extensions that declare `Py_MOD_GIL_NOT_USED` run without the GIL, legacy ones re-enable it inside the island only | Confined to the island |
| Allocator contention and object freelists | mimalloc (MIT) per-thread heaps; per-thread freelists for small ints, tuples and frames | None |

Two semantics need writing down, because CPython leaves them implicit. First, the dialect should state a memory model for shared containers: operations on one `list` or `dict` are atomic and linearisable, nothing else is ordered, and iteration under concurrent mutation raises as it does today. Second, `threading` maps onto `std::jthread` with `stop_token`, and the compiled program must never run Python finalisers from the collector thread; finalisation is queued back to the owning thread, as Oilpan does for destructors.

What this buys. CPU-bound Python code that uses `threading` scales across cores without `multiprocessing`; `asyncio` code gains a real multi-threaded scheduler through `std::execution`; and the single-thread cost is a few percent from biased counting, the same order free-threaded CPython reports, minus whatever the elision passes remove.

## 8. Libraries: compiling, linking, precompiled binaries

A dependency manifest assigns every package one of four strategies, and the build never recompiles a package whose content hash and dialect version are unchanged. This is where the project either becomes usable or stalls, because the Python ecosystem's value is in packages whose implementation is C against the CPython API.

| Package class | Examples | Strategy | Speed | Source hidden |
| --- | --- | --- | --- | --- |
| Pure Python | `attrs`, `click`, `requests`, most stdlib `.py` modules (`argparse`, `dataclasses`, `functools`, `heapq`, `_pydatetime`, `_pydecimal`) | Compiled through the pipeline once into a static library plus a typed interface file; stored as a binary artefact keyed by content hash, dialect version and toolchain ABI | Native | Yes |
| Stdlib C modules | `math`, `itertools`, `collections`, `json`, `re`, `random`, `os.path`, `hashlib`, `sqlite3` | Intent mapping onto C++ std and MIT/BSD libraries (section 12); the stdlib's pure-Python fallbacks (`_pyio`, `_pydecimal`) compile as ordinary Python where no mapping exists | Native | Not applicable |
| C-extension packages on the CPython API | `numpy`, `pandas`, `scipy`, `pydantic-core`, `orjson`, `pillow`, `torch` | Intent mapping where a C++ counterpart exists (numpy slices onto `std::mdspan`, `std::linalg`, `std::simd`, xtensor or Kokkos); otherwise the package runs inside an embedded free-threaded CPython island behind a bridge | Native, or one boundary crossing per call into the island | The island's own `.pyc` and `.so` files stay as they are |
| `ctypes` and `cffi` ABI-mode users | Thin wrappers over C libraries | Declarations lowered to `extern "C"` prototypes and direct calls | Faster than `ctypes` | Yes |

The typed interface file is the contract between packages. It carries exported signatures with oracle-inferred types, frozen class layouts, cycle-freedom and thread-locality facts, purity and escape summaries per function (so `json.dumps(x)` is known not to retain `x`), and the generic bodies that must instantiate at the call site. It plays the role of Rust's `.rmeta` and Swift's `.swiftinterface`, and it is what lets the ownership pass work across a binary boundary.

Separate compilation versus whole program. Ownership and devirtualisation want the whole program; incremental builds and binary libraries want separate compilation. The resolution is the one Swift and Rust use: non-generic code compiles into the static library, generic and small inlinable code ships in the interface, and final-link LTO (`-flto` with whole-program vtable optimisation in both GCC and Clang) recovers closed-world devirtualisation across libraries. C++20 modules (one module unit per Python module, a built module interface per package) keep the compile time of the user's own source small.

The embedded-CPython bridge is version-specific: the free-threaded 3.14 build supports neither the Limited API nor the stable ABI, so the bridge is built against the full C API of one pinned 3.14t minor and rebuilt per Python release, and it generates a `PyTypeObject` proxy for every frozen class that crosses the boundary, as Cython does for `cdef` classes. HPy would have been the cleaner ABI to implement natively, but [its maintainers have stopped active development](https://github.com/hpyproject/hpy) and point to the PyNI PEP work as the successor; it is not a foundation to build on today.

Toolchain pinning. C++ has no ABI across compilers and standard libraries, so the precompiled artefact key must include compiler, standard library, ABI flags and the runtime's version; a cache miss on any of them rebuilds the package from its stored intermediate IR, which is cheaper than from source because every proof is already recorded.

## 9. C++23/26 feature map

Target C++26 on GCC 16 only, with no C++23 fallback (decision of 2026-10-30; design document, section 10.3): [the committee finished C++26 in March 2026](https://herbsutter.com/2026/03/), GCC 16.1 ships most of it including reflection behind `-freflection`, and Clang's reflection lives only in [Bloomberg's experimental fork](https://github.com/bloomberg/clang-p2996), which its authors say not to use for production artefacts. Pattern matching (P2688) did not make C++26 and is aimed at C++29, so `match` lowers to `std::variant` and `std::visit`.

One point matters more than any row below: the rewriter does not need C++26 reflection for the code it generates, because it already holds the Python class layouts. Reflection pays off in the hand-written runtime (generic `__repr__`, `__eq__`, hashing, pickling, keyword-argument binding from parameter reflection) and in user-supplied C++ that the dialect lets programs call.

| Python construct | C++ facility | Standard | Status in GCC 16 / Clang 21 (Oct 2026) |
| --- | --- | --- | --- |
| `typing.Protocol`, duck-typed parameters | Concepts | C++20 | Shipping |
| Comprehensions, `map`/`filter`, `itertools` (`zip`, `enumerate`, `chain`, `product`, `pairwise`, `batched`, `groupby`, `islice`, `repeat`) | Ranges: `views::zip`, `enumerate`, `concat`, `cartesian_product`, `adjacent<2>`, `chunk`, `chunk_by`, `take`/`drop`, `repeat`; `ranges::to` | C++20/23, `concat` C++26 | Shipping except `concat` (GCC 15+) |
| `sum`, `functools.reduce`, `any`/`all`, `in`, `min`/`max` | `ranges::fold_left`, `any_of`/`all_of`, `ranges::contains`, `ranges::min`/`max` | C++23 | Shipping |
| `str.join`, `str.split`, `in` on strings | `views::join_with`, `views::split`, `string::contains` | C++23 | Shipping |
| f-strings, `%`, `.format` with runtime strings, `print` | `std::format`, `std::runtime_format`, `std::print`/`println` | C++20/23/26 | Shipping |
| `repr(float)`, `int(s)`, `float(s)` | `std::to_chars`, `std::from_chars` | C++17 | Shipping |
| Generator functions | `std::generator<T>` | C++23 | Shipping (libstdc++ 14+, libc++ 19+) |
| `async def`, `await`, `asyncio.gather`, thread pools | Coroutines; `std::execution` senders, schedulers, `when_all`, `execution::task` | C++20/26 | Library implementations still landing; the NVIDIA reference `stdexec` is Apache-2.0 with LLVM exception, so wait for the standard library or write a thin MIT scheduler over libuv |
| `try`/`except` used for local control flow | `std::expected` with monadic `and_then`/`or_else` | C++23 | Shipping |
| `with` | RAII guard types | C++11 | Shipping |
| `@dataclass(order=True)`, `__eq__`, `__lt__` | Aggregates with defaulted `operator<=>` | C++20 | Shipping |
| `**kwargs` to a known callee | Designated initialisers; parameter reflection in the runtime | C++20/26 | Shipping / GCC only |
| Mixins, `self` as explicit receiver | Deducing this (explicit object parameter) | C++23 | Shipping |
| `enum.Enum` | `enum class` plus reflection-generated names | C++11/26 | Shipping / GCC only |
| `Optional[T]`, \`T | None\` | `std::optional<T>`, `std::optional<T&>` | C++17/26 |
| Callbacks, first-class functions | `std::function_ref`, `std::copyable_function`, `std::move_only_function` | C++23/26 | Partial |
| Small tuples, `*args` of bounded arity | `std::inplace_vector` | C++26 | GCC 15+ |
| Object references with value semantics when proven unique | `std::indirect`, `std::polymorphic` | C++26 | GCC 16 |
| `numpy` views, `@` operator, elementwise loops | `std::mdspan`, `std::submdspan`, `std::linalg`, `std::simd` | C++23/26 | `mdspan` shipping; `linalg` partial; `simd` GCC 15+ |
| Runtime's lock-free tables, deferred reclamation | `std::hazard_pointer`, `std::rcu_domain` | C++26 | Experimental in GCC; xenium (MIT) meanwhile |
| `assert`, type guards, dialect preconditions | Contracts (`pre`, `post`, `contract_assert`) | C++26 | GCC trunk; Clang experimental |
| `random`, `datetime`, `pathlib`, `struct` | `<random>`, `<chrono>` calendars and time zones, `<filesystem>`, `std::bit_cast`/`std::byteswap` | C++11/20/23 | Shipping |
| Tracebacks on demand | `std::stacktrace` | C++23 | Shipping |
| Unreachable branches after exhaustive `match` | `std::unreachable` | C++23 | Shipping |
| Bundled constant data (frozen module snapshots) | `#embed` | C++26 | Shipping |

On continuations: C++20 coroutines are stackless, one-shot continuations, which covers generators, `async` and `send`/`throw` with a custom promise. Stackful coroutines (greenlet, gevent) are not in the standard; `minicoro` (MIT) covers them if the dialect admits them.

## 10. Source visibility (requirement dropped)

Hiding the Python source is no longer a requirement: an optimised, stripped native binary is already impractical to reverse into Python, and the hashed attribute names and name-stripping of the first draft would only have cost readability. The generated C++ is now meant to be read: Python identifiers kept, docstrings and comments carried as `//` lines, one C++ module unit per Python module, and a source map from every statement to its Python line.

That makes the output debuggable with ordinary tools and lets a team keep a module in C++ later and retire the Python original. What stays visible in the binary, as in any native program: string literals, class names used by `__repr__`, exception messages, and everything inside the embedded-CPython island.

## 11. Performance expectations

Speed comes from what the passes prove, so the honest forecast is by code class, measured against CPython 3.14 and matching what Codon, mypyc and Cython report for the same classes.

| Code class | Expected speedup | What drives it |
| --- | --- | --- |
| Typed numeric loops, scalar arithmetic, small structs | 10-100x | Unboxed `int64_t`/`double`, bounds checks removed, `std::simd` where loops vectorise |
| Object-heavy code with frozen classes and inferred types | 3-10x | Fixed layouts, devirtualised calls, value containers, arena allocation |
| Dynamic residue (`Any`, unions, `__getattr__` classes) | 1.5-3x | Boxed objects with inline caches; still faster than the interpreter loop |
| String and dict heavy code | 1-3x | CPython's `str` and `dict` are already C; gains come from avoided boxing and interning |
| I/O-bound and island-bridged code | About 1x | Bound by the kernel, the network, or boundary crossings into embedded CPython |
| Multi-threaded CPU-bound code | Near-linear with cores | No GIL; biased counting keeps single-thread cost within a few percent |

The failure mode to design against is a compiled program slower than CPython: boxing everywhere plus atomic counting on every touch. The elision passes (ownership, thread-locality, cycle-freedom) exist to prevent exactly that, and the benchmark suite should include a worst-case untyped program to keep the floor visible.

## 12. Components under MIT/BSD

Everything linked into the output or into the compiler can be MIT, BSD or ISC; the three exceptions are tools or system runtimes that attach no obligation to the output, and they are flagged for a decision.

| Role | Candidate | Licence | Note |
| --- | --- | --- | --- |
| Python frontend | CPython `ast` and `tokenize` | PSF-2.0 | Permissive, GPL-compatible, not literally MIT/BSD; the compiler is a Python program, so it uses them at build time only. Decision needed |
| Lossless parsing | libcst, parso, tree-sitter-python | MIT | Any of the three; libcst keeps formatting and comments |
| Type oracle | mypy; pyrefly; ty | MIT | mypy as a library is the mypyc-proven route; pyrefly and ty are faster and younger |
| Reference compiler design | RPython (PyPy), py2many | MIT | RPython's annotator and rtyper are the most mature restricted-Python-to-C pipeline; [py2many](https://github.com/py2many/py2many) is a shallow AST-rewriting Python-to-C++ transpiler worth forking for its scaffolding |
| Allocator | mimalloc | MIT | Per-thread heaps, heap walking |
| Hash maps and sets | ankerl::unordered\_dense; tsl::ordered\_map; tsl::robin\_map | MIT | Ordered map only for small static dicts; the Python dict is the runtime's own compact map |
| Deferred reclamation before C++26 ships it | xenium (hazard pointers, epoch reclamation) | MIT | Replaced by `std::hazard_pointer`/`std::rcu_domain` when standard libraries land them |
| Bigint | libtommath | Unlicense/public domain | Or an in-house schoolbook plus Karatsuba; CPython's `longobject.c` is PSF, so it is a reference, not a copy |
| Regular expressions | PCRE2; RE2 | BSD-3 | PCRE2 matches Python's `re` semantics (backreferences, lookbehind); RE2 is faster but lacks them |
| JSON | yyjson; glaze; nlohmann/json | MIT | glaze uses C++23 reflection-like aggregate introspection for struct mapping |
| Event loop and sockets | libuv | MIT | Backs the `asyncio` port; a scheduler adapter exposes it as a `std::execution` scheduler |
| HTTP client (`requests`, `httpx` intent) | cpp-httplib; cpr | MIT |  |
| Logging, CLI | spdlog; CLI11 | MIT; BSD-3 | `logging` and `argparse` intents |
| Hashing and crypto (`hashlib`, `hmac`, `secrets`) | libsodium; BearSSL | ISC; MIT | OpenSSL is Apache-2.0, so avoided |
| SQLite | SQLite | Public domain | `sqlite3` intent |
| Compression | zlib; zstd | zlib licence; BSD-3 | `zlib`, `compression.zstd` intents |
| Images (`pillow` subset) | stb\_image, stb\_image\_write | MIT or public domain |  |
| Arrays and linear algebra (`numpy` intent) | xtensor; Kokkos; `std::mdspan`/`std::linalg`/`std::simd` | BSD-3; BSD-3; standard | Eigen is MPL-2.0 and Arrow is Apache-2.0, so both are out |
| Dataframes (`pandas` intent) | hosseinmoein/DataFrame | BSD-3 | Narrower than pandas; the island covers the rest |
| Stackful coroutines (greenlet intent) | minicoro | MIT | Only if the dialect admits them |
| Tracing collector, if ever added | cppgc (V8), MMTk | BSD-3; Apache-2.0 or MIT | Not in the recommended design |
| Test harness for generated C++ | doctest; GoogleTest | MIT; BSD-3 |  |
| Build | CMake, Ninja, ccache or sccache | BSD-3; Apache-2.0; GPL-3 / Apache-2.0 | Tools run as processes; nothing links into the output. Decision needed only if the user wants tools under MIT/BSD too |
| C++ compiler | GCC 16; Clang 21 | GPL-3 with runtime exception; Apache-2.0 with LLVM exception | Both exceptions make the compiled output unencumbered; neither is MIT/BSD. Decision needed. Embedding libclang or LLVM as a library would pull Apache-2.0 code into the compiler, so the design keeps the C++ compiler as an external process |
| C++ standard library | libstdc++; libc++ | GPL-3 with runtime exception; Apache-2.0 with LLVM exception | System runtime; same decision as the compiler |
| Embedded Python island | CPython 3.14t | PSF-2.0 | Only for packages assigned to the island |

Excluded for licence reasons: Boost (BSL-1.0, permissive but not MIT/BSD), Codon (Apache-2.0 since 2025, [previously BSL](https://tech.slashdot.org/story/25/03/16/003225/)), Abseil (Apache-2.0), folly (Apache-2.0), stdexec (Apache-2.0 with LLVM exception), Eigen (MPL-2.0), GMP (LGPL), Shed Skin (GPL).

## 13. Lessons from prior art

None of these is the method to adopt; each one has paid for a lesson the pass design above is built around.

| Project | Licence | What it does | The lesson |
| --- | --- | --- | --- |
| Nuitka | Apache-2.0 | Translates control flow to C, keeps every CPython object and API call | Full compatibility with 1.5-4x speed: translating syntax without types buys little, and the source stays recoverable from the constant blobs |
| Cython, mypyc | Apache-2.0, MIT | C output; typed parts native, untyped parts through the CPython API | The boxed fallback must be first-class; mypyc proves a type checker can be the compiler's oracle |
| Codon | Apache-2.0 (BSL until 2025) | Own typed dialect, LLVM, Boehm GC, no CPython object model | 10-100x is reachable, but its 64-bit `int`, ASCII strings and unordered dicts show what happens when a dialect changes observable semantics: users cannot trust results |
| Shed Skin | GPL | Restricted Python to C++ with whole-program iterative inference | Inference alone does not scale past small programs; annotations plus an oracle do |
| RPython (PyPy toolchain) | MIT | Restricted Python compiled to C after executing module-level code at compile time | Compile-time staging of class and module bodies removes most metaprogramming from the runtime; the annotator/rtyper split is a working multi-level IR |
| Pythran | BSD-3 | Numeric kernels to C++ with expression templates | The closest prior use of C++ as an intent target; its limits (one module, numeric only) come from having no runtime object model |
| py2many | MIT | AST-rewriting transpiler to C++, Rust, Go and others | The pass-over-AST scaffolding exists and is MIT; it stops at syntax, so it shows where the type and ownership passes must begin |
| Free-threaded CPython (PEP 703, 3.13-3.14) | PSF | Biased counting, immortal objects, deferred counting, per-object critical sections, mimalloc | The complete recipe for counting without a GIL, measured in production |
| CPython 3.14.5 collector revert | PSF | Incremental collector withdrawn for memory pressure | Latency targets without growth bounds fail in production; the collector needs a governor |
| Oilpan (cppgc), MMTk LXR | BSD-3, MIT/Apache | Concurrent tracing in C++; counting plus Immix | Concurrent tracers still need short atomic pauses and precise or conservative roots; counting plus trial deletion needs neither |
| HPy | MIT | Universal, GIL-agnostic C API for extensions | A better extension ABI exists on paper and is now unmaintained; do not build the bridge on it |

## 14. Risks, effort, phased plan

The dominant risk is scope: the dynamic-residue runtime grows into a second CPython. The dialect document and the compile-time staging pass are the two controls, and every phase below ends with a gate that measures them.

| Risk | Likelihood | Mitigation |
| --- | --- | --- |
| Runtime object model grows into a second interpreter | High | Dialect rejects reflection over live code; staging removes definition-time dynamism; a size budget on the runtime (lines and binary bytes) enforced in CI |
| C++ compile times from templates, ranges and modules | High | One module unit per Python module, built module interfaces per package, explicit instantiation of common containers, content-hash caching of package binaries |
| Ecosystem gap (`numpy`, `pandas`, `torch`) | High | Island bridge first, intent mappings by usage frequency; a program is never blocked, only slowed, by a package in the island |
| Collector correctness (concurrent trial deletion, finaliser ordering) | Medium | Ship with a synchronous per-thread collector first; make it concurrent once differential tests are green; stress with ThreadSanitizer builds |
| Semantic drift (floor division, `bool`/`int`, string indexing, dict order) | Medium | Differential testing against CPython on the project's suite plus a conformance corpus; no deviation ships undocumented |
| C++26 compiler timing (Clang reflection experimental, `std::execution` landing) | Medium | Reflection confined to the hand-written runtime; C++23 profile for everything generated; `std::execution` behind an interface with a libuv scheduler |
| ABI drift across toolchains breaks precompiled packages | Medium | Artefact key includes compiler, standard library, ABI flags and runtime version; rebuild from stored IR on miss |

Effort, assuming experienced compiler engineers: a minimum viable compiler (typed subset, frozen classes, lists, dicts, strings, big ints, exceptions, generators; counting with a synchronous collector; single thread) is 6-12 engineer-months. A production system (stdlib coverage, island bridge, precompiled packages, concurrent collector, GIL-free runtime, build caching, packaging) is 3-5 engineer-years. For scale: Codon took a funded team about four years to reach a stable release, Nuitka is fifteen years of mostly one person, and mypyc is a multi-year side project of the mypy team.

Phases, each with its gate:

1. Dialect and harness. Write the dialect specification, the IR schemas, the differential test runner and a conformance corpus. Gate: the corpus runs under CPython and the harness detects a planted deviation.
2. Typed subset. Frontend, staging, desugaring, oracle integration, typed IR, C++23 emitter; runtime v0 with counting and no cycle collector. Gate: a benchmark set of typed numeric programs runs 10x faster than CPython 3.14 with identical output.
3. Ownership and the object model. Escape analysis, arenas, box elimination, hidden-class dynamic objects, strings and dicts in the runtime, generators, the synchronous per-thread cycle collector. Gate: an untyped program is never slower than CPython; a graph-heavy program frees its cycles.
4. Packages. Interface files, per-package static libraries and module interfaces, content-hash cache, stdlib pure-Python compilation, the embedded 3.14t island with proxies for frozen classes. Gate: a real application with `numpy` in the island and everything else compiled builds incrementally in under a minute.
5. Threads. Biased counting, per-object locks with thread-locality elision, hazard-pointer tables, concurrent trial deletion, `threading` and `asyncio` on `std::execution` over libuv. Gate: a CPU-bound threaded benchmark scales near-linearly to eight cores; ThreadSanitizer is clean; tail pauses stay under one millisecond.
6. C++26 adoption. Reflection in the runtime for `repr`, equality, hashing and pickling; `std::simd` and `std::linalg` for numeric intents; `std::execution::task`; `std::hazard_pointer` and `std::rcu_domain` replacing xenium. Gate: every optimising pass at rung 2 of the proof ladder or higher, on GCC 16; Clang is not a target.

The first useful deliverable is at the end of phase 2: a compiler for typed Python modules that produces linkable C++ libraries and executables, which is already a product (a mypyc or Pythran replacement with hidden source) before any of the harder runtime work exists.

## Sources

Looked up on 2026-10-28; everything else in this study is design reasoning from the author's own knowledge of the compilers and runtimes named.

- [C++26 is done: trip report, March 2026 ISO C++ meeting (Herb Sutter)](https://herbsutter.com/2026/03/) — reflection, `std::execution`, contracts, GCC trunk status
- [libc++ C++26 status](https://libcxx.llvm.org/Status/Cxx26.html) — adoption meetings for hazard pointers, RCU, `std::execution`, trivial relocation, `indirect`/`polymorphic`, reflection papers
- [C++26 (Wikipedia)](https://en.wikipedia.org/wiki/C++26) — GCC 16.1 coverage, `<hazard_pointer>`, `<rcu>`, `<simd>`, `execution::task`
- [Bloomberg clang-p2996 fork](https://github.com/bloomberg/clang-p2996) — experimental status of Clang reflection
- [reflect-cpp C++26 reflection notes](https://rfl.getml.com/cpp26_reflection) — `-freflection` on GCC 16.2, `-freflection-latest` on Clang fork
- [P2688R4 Pattern Matching: match expression](https://open-std.org/jtc1/sc22/wg21/docs/papers/2024/p2688r4.html) — C++29 targeting poll
- [Python 3.14.5 release page](https://www.python.org/downloads/release/python-3145/) — PEP 779 free-threading support, incremental collector reverted
- [cppgc / Oilpan README](https://chromium.googlesource.com/v8/v8.git/+/HEAD/include/cppgc/README.md) — concurrent marking and sweeping, thread-local heaps, conservative stack scanning
- [mmtk-core](https://github.com/mmtk/mmtk-core) and [LXR paper](https://arxiv.org/abs/2210.17175v1) — dual MIT/Apache licence; counting plus Immix plus concurrent tracing
- [HPy repository](https://github.com/hpyproject/hpy) — no longer actively maintained; PyNI PEP work as successor
- [py2many](https://github.com/py2many/py2many) — MIT, Python-to-C++ among other targets
- [Codon licence change to Apache-2.0](https://tech.slashdot.org/story/25/03/16/003225/)
