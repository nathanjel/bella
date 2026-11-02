# The C++ emitter and the runtime core (step 3 of the C++ leg)

Status: step 3a.1, 2026-11-02. `pipeline/backend/cpp.py` turns an L2 module (`docs/l2.md`) into
one C++26 translation unit against `runtime/include/bella/runtime.hpp`; `pipeline/build.py`
compiles it and links it with the runtime library. The slice examples (`make slice`) and
`pipeline/tests/test_compiled.py` pass; the corpus under the compiled runner is `make
compiled-corpus`, against `conformance/evalc-baseline.txt`. The toy emitter from L1 is gone.

## 1. Where things live (decided 2026-11-02, `docs/DECISIONS.md`)

C++ holds storage and the hot primitives; whatever is defined by other Python operations is
Python in `runtime/prelude/`, compiled by Bella like any program.

| Part | Where | What |
| --- | --- | --- |
| The object model | `runtime/include/bella/object.hpp` | values (`Obj`, `Ref`), counting, classes, instances, attribute lookup, inline caches, deaths in CPython's order; tested three ways by `make object-test` |
| Exact `int` | `runtime/include/bella/int.hpp` | the 63-bit fast paths, tested by `make int-test`; the runtime calls them and turns their C++ errors into Python exceptions |
| The runtime core | `runtime/include/bella/runtime.hpp`, `runtime/src/*.cpp` | `str` (PEP 393), tuple, list, CPython's compact dict, hashing (SipHash-1-3 keyed as `PYTHONHASHSEED` says, `int` and `tuple` hashes as CPython's), the call protocol and argument binding, function objects and cells, modules and names, the exception carrier and frame records, iteration, operators, `sys.stdout` |
| The prelude | `runtime/prelude/builtins.py` | `print` so far; CPython runs it against the builtin in `runtime/tests/test_prelude.py` |

`object.hpp`'s `Str` is the real `str` now (PEP 393 code units beside the UTF-8 text the attribute
code reads), and its kinds include the runtime's, whose deaths the runtime registers (`destroyer`).
`object.hpp`'s `call` reaches every callable through the runtime's hook, so a descriptor or a
finaliser written in Python runs from the attribute machinery.

## 2. What generated code looks like

`fib.py`'s function (`pipeline/examples/out/fib.cpp`):

```cpp
static Ref f_fib(rt::PyFunction* self, rt::Args args) {
    Ref n;
    rt::FrameGuard frame(code_fib, n);
    rt::bind(self, args, {&n});
    Ref t1, t2, t3, t4, t5, t6, t7, t8, t9, t10, t11, t12, t13;
    frame.line = 5;
    t1 = rt::load_fast(n, "n");
    t2 = rt::compare(rt::CmpOp::Lt, t1.get(), Obj::small(2));
    t1 = Ref{};
    t3 = rt::truth_ref(t2.get());
    t2 = Ref{};
    if (rt::test(t3)) {
        ...
```

* One C++ function per code object, named after its qualified name; a module body is
  `module_body(Module*)`. Python locals keep their names (`py_` in front where C++ reserves the
  name or the emitter uses it); runtime calls are qualified (`rt::`), so no Python name shadows
  them.
* One C++ statement per L2 statement, in L2's order; `frame.line = n` for L2's `line n`.
* Temporaries are `Ref`s declared at the top of their region (the function, a `try` body, a
  handler, a `finally` block) in their number order, so C++ unwinding destroys them newest first:
  L2's exception edge (`docs/l2.md` section 8, decision 1). `release t` is `t = Ref{}`; a store
  moves its value in, and the old value is released after the new one is stored.
* The frame record and guard of decision 5: `FrameGuard frame(code_f, locals...)` after the
  locals. When an exception leaves the function, the guard appends `(code, line)` to the
  exception's `__traceback__` and moves the locals into that entry, so they die with the
  traceback. The guard also counts the recursion depth (spec D-17: `RecursionError` past 1000).
* Exceptions are C++ exceptions (decision 4): `rt::PyError` carries the Python exception. An
  `except` clause is a `catch (rt::PyError&)` that matches its clauses in order and rethrows when
  none matches; a `Handling` scope makes the exception the one being handled, for a bare `raise`
  and for `__context__`. The synthetic variables a `try` body stored are set to None before the
  handlers, after the body's temporaries, as `eval2` does (review log RL-186).
* C++ has no `finally`: the block is written out on every way out of the `try`, as CPython's
  compiler does: the normal end, the exception edge (`catch (...)` and rethrow), and before every
  `return`, `break` or `continue` that leaves it, innermost first. A loop's held iterator is
  released where L2 says, after the `finally` blocks nested in the loop. `return` moves its value
  into `ret` before the `finally` blocks run. `except ... as e`'s `e = None; del e` is a `finally`
  of the handler.
* Constants: small ints are immediates (`Obj::small(2)`), strings are interned, tuples of those
  are made when the module first runs. A constant the runtime cannot make yet (a float, bytes, an
  int beyond 62 bits) is refused where it is used, never when the module starts (P-1).

## 3. Building and running

`python3 pipeline/build.py --run prog.py args...` lowers the program, emits it into
`build/compiled/<name>-<hash>/`, compiles it at `-O1` and links it with `libbella.a`, which is the
runtime sources and the compiled prelude at `-O2`, built once per content hash (sources, prelude,
the compiler's own Python, the flags) under a lock, so parallel builds share it. The program's
`main` is `run_main`: the builtins module and `sys`, the prelude modules (each `__all__` goes into
builtins), then `__main__`. At the end `__main__`'s globals are released in insertion order (as
CPython 3.15.2 does, measured), stdout is flushed, and an uncaught exception prints a traceback of
file and line (spec D-06) and exits 1; a facility Bella lacks yet stops with
`bella: not implemented: ...` and exit 70, as the evaluators refuse.

## 4. Gaps, in the order the steps close them

* 3a.2: classes (`__build_class__` from the prelude, class bodies, `classdict` loads), instances
  of user classes in operators, truth, `str()`, iteration and calls; the exception classes move to
  the prelude; the containers' `repr` (prelude); `set`. C-3-05..11.
* 3a.3: instance dicts as real dicts (`vars()`, `__dict__`): C-3-01..03.
* 3b: generators (state machines, design section 10.3) and compiled imports: C-3-04.
* 3c: the cycle collector and weak references, model first: C-3-12, which closes task 3.
* Later: `float` beyond the digits (the wrapper of `to_chars`/`from_chars`), the `bn` copy for
  big ints, `format` specifications, the global read caches of decision 6, the Unicode database
  for `repr` beyond Latin-1, the rest of the builtins.
* Speed is not a goal yet: everything is boxed and every call binds generically, so the compiled
  `fib` takes about twice CPython's time. Phase 2's types change that.
