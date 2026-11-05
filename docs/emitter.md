# The C++ emitter and the runtime core (step 3 of the C++ leg)

Status: step 3b under way, 2026-11-03. `pipeline/backend/cpp.py` turns an L2 module (`docs/l2.md`)
into one C++26 translation unit against `runtime/include/bella/runtime.hpp`; `pipeline/build.py`
compiles the program's modules and links them with the runtime library. The slice examples
(`make slice`), `pipeline/tests/test_compiled.py` and the cases of
`conformance/evalc-baseline.txt` pass compiled (`make compiled-corpus`, 31 of 84: most of the rest
stop on a native module of the standard library's, which step 3b provides next). The toy emitter from L1 is gone.

## 1. Where things live (decided 2026-11-02, `docs/DECISIONS.md`)

C++ holds storage and the hot primitives; whatever is defined by other Python operations is
Python in `runtime/prelude/`, compiled by Bella like any program.

| Part | Where | What |
| --- | --- | --- |
| The object model | `runtime/include/bella/object.hpp` | values (`Obj`, `Ref`), counting, classes, instances, attribute lookup, inline caches, deaths in CPython's order; tested three ways by `make object-test` |
| Exact `int` | `runtime/include/bella/int.hpp`, `runtime/src/bigint.cpp`, `runtime/src/bn.inc` | the 63-bit fast paths, tested by `make int-test`, which say when a result does not fit; then the Python layer in `bigint.cpp` over a copy of SEL's `bn` (case C-6-10) |
| The runtime core | `runtime/include/bella/runtime.hpp`, `runtime/src/*.cpp` | `str` (PEP 393), tuple, list, CPython's compact dict, hashing (SipHash-1-3 keyed as `PYTHONHASHSEED` says, `int` and `tuple` hashes as CPython's), the call protocol and argument binding, function objects and cells, modules and names, the exception carrier and frame records, iteration, operators, `sys.stdout` |
| The prelude | `runtime/prelude/build_class.py`, `builtins.py` | `__build_class__`; `print`; `property`, `staticmethod`, `classmethod`; the `repr` of lists, tuples, dicts, sets and frozensets (installed as their `__repr__`, each checking its receiver). CPython runs each against its builtin in `runtime/tests/test_prelude.py`. What a module exports looks like CPython's builtin: a function is a `builtin_function_or_method` (its repr, its `__self__`, never bound as a method), a class is immutable (RL-217) |
| Types and classes | `runtime/src/types.cpp`, `set.cpp` | the builtin types' attributes as getset and method descriptors; `type.__new__` and calling a class; attribute access on classes and on the C++ types' objects; special-method dispatch; `set` and `frozenset` as CPython's table (`Objects/setobject.c`), so their order is CPython's (D-05) |

`object.hpp`'s `Str` is the real `str` now (PEP 393 code units beside the UTF-8 text the attribute
code reads), and its kinds include the runtime's, whose deaths the runtime registers (`destroyer`).
`object.hpp`'s `call` reaches every callable through the runtime's hook, so a descriptor or a
finaliser written in Python runs from the attribute machinery; an exception a finaliser raises is
reported as CPython reports an unraisable one and dropped (RL-191).

A name CPython has and the runtime lacks yet is refused, never answered with NameError or
AttributeError (RL-211): `tools/cpython_names.py` records from the pinned CPython the builtins, a
script's globals, `sys` and each built-in type's own attributes with their kinds
(`runtime/src/cpython_names.inc`, checked by `make verify`). A lookup that finds nothing consults
it before `__getattr__` runs: `"a".startswith("a")` stops with `bella: not implemented:
str.startswith (…)` and exit 70, while `"a".nosuch` raises AttributeError as in CPython. The same
table says which methods CPython keeps as slot wrappers; the runtime holds those as method
descriptors and refuses their repr and type (RL-218). It also records which operators CPython
handles between the built-in types (and an instance whose own methods declined): an operator
the runtime lacks there (`str %`, `type | type`) is refused, while one CPython rejects too still
raises CPython's TypeError.

Operators follow `abstract.c`: `binary_op1` tries the number slots (the C++ types' own:
`int` arithmetic, the set operators, `dict |`; then the operands' methods), and only then the
sequence slots, concatenation by the left operand and repetition by either, so `+=` defers to a
right operand's `__radd__` before it extends a list, and `*=` repeats a list in place. Sets
compute `|`, `&`, `-` and `^` by `setobject.c`'s algorithms, whose order of insertion decides the
result's iteration order (`set_merge` copies slots in place into an empty table of the same
size). Dicts, sets, ranges and slices compare as CPython's do; the empty tuple is one object.

## 2. What generated code looks like

`fib.py`'s function (`pipeline/examples/out/fib.cpp`):

```cpp
static Ref f_fib(rt::PyFunction* fn, rt::Args args) {
    Ref n;
    rt::FrameGuard frame(code_fib, n);
    rt::bind(fn, args, {&n});
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

* One C++ function per code object, named after its qualified name (`f_T_init` for `T.__init__`:
  runs of `_` folded, since C++ reserves `__`; the same on every run); a module body is
  `module_body(Module*)`, and the function object is the parameter `fn`. Python locals keep
  their names. A name C++ reserves, or one that matches the single pattern of the emitter's own
  names (`t3`, `fin2`, `S_x`, `code_f`, `py…`), is escaped injectively: `py`, then the name with
  `_` written `_1` and a non-ASCII character `_2` and its code point (RL-207, RL-219). Runtime
  calls are qualified (`rt::`), so no Python name shadows them.
* One C++ statement per L2 statement, in L2's order; `frame.line = n` for L2's `line n`.
* Temporaries are `Ref`s declared at the top of their region (the function, a `try` body, a
  handler, a `finally` block) in their number order, so C++ unwinding destroys them newest first:
  L2's exception edge (`docs/l2.md` section 8, decision 1). `release t` is `t = Ref{}`; a store
  moves its value in, and the old value is released after the new one is stored.
* The frame record and guard of decision 5: `FrameGuard frame(code_f, locals...)` after the
  locals. An exception is recorded where it arrives in the frame (D-12, RL-221): every catch the
  emitter writes starts with `frame.arrived(e)`, which prepends `(code, frame.line)` to the
  exception's `__traceback__` unless this frame has already recorded that throw (the `PyError`
  carries the recording frame's id) or re-raises it bare; the guard records an exception that no
  catch of the frame saw. When an exception leaves the function, the guard moves the locals into
  the frame's newest entry, so they die with the traceback, and clears the mark so that the
  caller records the call. A caught exception does not keep the locals yet (RL-222, step 3c).
  Code CPython runs without a frame, the prelude and an inlined comprehension, has
  `Code::shown` false and is never recorded (RL-223, RL-224). The guard also counts the recursion
  depth (spec D-17: `RecursionError` past 1000).
* Exceptions are C++ exceptions (decision 4): `rt::PyError` carries the Python exception. An
  `except` clause is a `catch (rt::PyError&)` that matches its clauses in order and rethrows when
  none matches; a `Handling` scope makes the exception the one being handled, for a bare `raise`
  and for `__context__`. A clause's types are evaluated at the `except` line and all checked
  before any is matched (`CHECK_EXC_MATCH`, RL-228, RL-238). The synthetic variables a `try` body
  stored are set to None before the handlers, after the body's temporaries, as `eval2` does
  (review log RL-186).
* An exception's `args`, `__traceback__`, `__cause__`, `__context__` and `__suppress_context__`
  (AttributeError's `name` and `obj`, NameError's `name`) are fields of the object, not entries of
  its `__dict__` (`rt::exception_field`): `object.hpp`'s native fields, from the model's
  `RefClass(native=...)`, behind BaseException's getsets with CPython's checks, released after the
  subclass's slots in `BaseException_clear`'s order (RL-230). A raise sets `__context__` as
  `_PyErr_SetObject` does, replacing an earlier one and cutting a link back that would make a cycle
  (RL-229); `raise ... from` is `do_raise`'s.
* C++ has no `finally`. A `try` with one gets a completion variable (`int fin2`): the normal
  end, and every `return`, `break`, `continue` or loop end leaving the `try`, set it and jump to
  the label after the `try`, where the block runs once, outside the `try`'s catch, and the
  completion goes on outward (to the next `finally`, the loop, or `return ret`). The exception
  edge is a catch of its own that runs the block with the exception as the one being handled (a
  bare `raise` re-raises it, a new exception takes it as `__context__`) and then
  `rt::rethrow`s it (RL-192, RL-193). A loop's held iterator is released where L2 says.
  `except ... as e`'s `e = None; del e` cannot raise and is written inline on every way out of
  the handler. Without a `finally` on the way, `return` releases the loops' holds and returns.
* The frontend's synthetic variables are what CPython keeps on its stack (a `with` statement's
  manager, a match subject, an inlined comprehension's iterator and result): when an exception
  leaves the function, a `StackValues` guard drops them, newest first, after the temporaries and
  before the frame guard records the real locals (RL-213, as `eval2` does, RL-186). Unpacking
  releases its source before the targets are bound (RL-194).
* Constants: small ints are immediates (`Obj::small(2)`), strings are interned, tuples of those
  are made when the module first runs. A float is a C++ hexadecimal literal, its exact bits. A constant the runtime
  cannot make yet is refused where it is used, never when the module starts (P-1).

## 3. Classes (step 3a.2)

A class statement is L1's `build_class(body, name, *bases, **kw)`: the prelude's
`__build_class__` (CPython's `builtin___build_class__`, in Python) calls the class body, a C++
function of the namespace, and then the metaclass, `type`. `type.__new__` is CPython's
`type_new_impl` in its order: `__qualname__`, `__classcell__` and `__classdictcell__` taken out of
the namespace, `__slots__` checked and mangled (a conflict with a class variable is a
`ValueError`), `__new__` made a static method and `__init_subclass__` a class method, `__doc__`
None when absent, `__hash__` None beside an `__eq__`, the object model's class
(`object.hpp`'s `make_class`) made, a `__dict__` descriptor when the class adds an instance dict,
`__set_name__` in attribute order, then the next class's `__init_subclass__` with the keywords.
Calling a class is `type_call`: `__new__`, then `__init__` when the result is an instance.

Lookups follow CPython's order: on the type, through the descriptor protocol.
Functions are non-data descriptors (`function.__get__` binds), C++ methods are method descriptors,
the type's own attributes (`__name__`, `__mro__`, `__dict__`, ...) are getset descriptors on
`type`, and `object.hpp` counts any object whose type has `__get__` as a descriptor. Operators
dispatch to special methods with CPython's protocols: `binary_op1` (the left operand's method,
unless the right operand's type is a subclass overriding the reflected one), `do_richcompare`
(the subclass's reflected method first, identity for `==` and `!=` at the end), `__bool__` then
`__len__` for truth, `__iter__` and `__next__` or the old `__getitem__` protocol for iteration,
`__contains__` or iteration for `in`. The C++ types take part with their own operations, which
answer NotImplemented to operands they do not know. A property or `__get__` written in Python
that raises AttributeError falls back to `__getattr__`, which is called as CPython's
`call_attribute` calls it, after the AttributeError is dropped (RL-214).

What the passing class cases show is narrower than these sentences: the first review of this
code (2026-11-03) found 23 places where a protocol, a container algorithm or class validation
was not yet CPython's, among them callbacks that mutate or raise, rejected calls and abrupt exits
(review log RL-188 to RL-210). Those boundaries are tested now: every reviewer's program, a
matrix of every way out of a `finally`, and the 31 L2 release-point probes compiled
(`pipeline/tests/test_review_2026_11_03.py`, `test_compiled_probes.py`). A boundary no test
covers yet is not claimed to be exact.

## 3a. Instance dicts (step 3a.3)

There is one dict type, `object.hpp`'s `DictObject`: CPython's compact dict (an index table
probed with the perturbation scheme over entries in insertion order), with any key, whose hash
and `==` come from the runtime (`key_hash_hook`, `key_eq_hook`; a lookup whose `__eq__` changed
the table starts again, as CPython's does). The runtime's `Dict` is that type, so `vars(obj)` and
`obj.__dict__` are ordinary dicts (design section 3): stable identity, a lifetime of their own,
any key, every method, shared and replaced (`obj.__dict__ = d`), and `del obj.__dict__` starts the
object afresh. An exposed dict is split as CPython's materialised dict is: its values die in the
class's shared-keys order. Measured on 3.15.2 and modelled first (`refmodel` `RefDict`): a key that
is not exactly a `str` and `popitem` make it ordinary, `clear` too unless its values are still
embedded in the live object it was exposed from, and `copy` is split as well. Each operation
calls back into keys as CPython's does (case C-6-09): one lookup per operation (`setdefault`,
`pop`), a store that takes the value only once its lookup succeeded, a resize that finds the free
slot without comparing (`find_empty_slot`), `copy` and merges by `copy_lock_held` and
`dict_dict_merge` (a clean dict cloned, table and all; stored hashes otherwise), `fromkeys` of a
dict or set by their stored hashes, and an iterator that counts the entries still to come
(RL-232 to RL-237, RL-252, RL-253). `list`, `dict`, `set` and the keys and items views are
unhashable (RL-248), and an unhashable key's error names the container (RL-249). `keys()`,
`values()` and `items()` are live views (their repr is the prelude's); their set operations and
set comparisons are refused until they exist. `pipeline/tests/test_compiled.py` checks the
model's scenarios compiled.

`super` is a C++ type (`runtime/src/super.cpp`, case C-3-32): `super(type, obj)` checks `obj` as
`supercheck` does, and its lookup walks the MRO of `obj`'s type after `type`, each class's own
dict, binding what it finds with `obj` (None for a class) and that type (`super_getattro`);
`__class__`, `__thisclass__`, `__self__` and `__self_class__` are the super's own, `super(T)` is
unbound until `__get__`. The zero-argument form is the frontend's `super` intrinsic, given the
`super` the function sees, its `__class__` cell and its first argument; with no frames to read,
a `super()` the compiler does not see as such (`s = super; s()`) is refused.

A metaclass is a class of the program's that derives from `type` (case C-3-33). `type.__new__`
computes the winning metaclass from the bases (`_PyType_CalculateMetaclass`, a conflict a
TypeError, another winner's own `__new__` called instead); a class whose metaclass is such a class
takes its behaviour from it, as an instance takes its from its class (`has_python_type`): its
`__call__` makes the instances, its data descriptors and `__setattr__`/`__delattr__` take stores,
its `__getattr__` answers what the lookup did not find, and its special methods serve operators,
comparisons, truth, `in`, subscripts, `repr`, `str` and `hash`. `isinstance` and `issubclass` are
`Objects/abstract.c`'s (an exact type first, type's own check for a class whose metaclass is
`type`, else the metaclass's `__instancecheck__`/`__subclasscheck__`), and `type` has
`__call__`, `__setattr__`, `__delattr__`, `__instancecheck__`, `__subclasscheck__` and
`__abstractmethods__` (which makes `object.__new__` refuse an abstract class) for metaclasses to
reach through `super()`. A store to a class attribute CPython's `type` keeps as a descriptor the
runtime lacks (`__type_params__`, `__basicsize__`, `__bases__`) is refused.

A subclass of a built-in type makes objects of the built-in's kind (decision 2026-11-03; case
C-3-34 for `dict`): an instance of a `dict` subclass is a `DictInstance`, `object.hpp`'s dict with
the class's attribute storage beside its entries (its slots, an instance `__dict__`), so every dict
operation takes it as a dict, and the attribute machinery, a template over the object type, takes it
as an instance. An operation calls the subclass's override where CPython's slot would
(`overrides_builtin`): `d[k]`, `d[k] = v`, `del d[k]`, `in`, `len`, iteration, comparisons and
operators, truth, `str`; `dict`'s own methods do the dict's operation (so an override may call
`dict.__getitem__(self, k)`), a missing key reaches `__missing__`, and merges, `copy` and
`dict(d)` read the entries unless the subclass overrides `__iter__`, then `keys()` and
`__getitem__`. A class body stores through a `__prepare__`'d subclass's `__setitem__`. It dies as
`subtype_dealloc` then `dict_dealloc` release it: slots, the instance dict, then the entries.
`dict()` has its constructor (`dict.__new__`, `dict.__init__`); `list(x)` asks an object of a
Python class for its length hint, `tuple(x)` does not (3.15). An instance of an `int` subclass is an
`IntInstance` (case C-3-35): its value and the class's attribute storage; it is an int to every
operation that takes one (`as_int`, PyLong_Check), the fast paths that skip the dispatch take exact
ints only (`as_exact_int`), and its class's overrides come first where CPython's would (a subclass's
reflected method before the int's). `int()` is `long_new_impl`: `PyNumber_Long` (an int as
itself, `__int__`, `__index__`, a str) and `PyLong_FromString`'s rules for an ASCII str (a str
beyond ASCII is refused: its digits and spaces need the Unicode database).

A built-in module may be written in Python: `itertools` (case C-7-20) is `runtime/prelude/itertools.py`
and `_operator` (case C-7-21) `runtime/prelude/_operator.py`, compiled with the prelude and run at the first import (`NATIVE_IN_PYTHON` in `pipeline/build.py`,
`fill_in_python` in `runtime/src/imports.cpp`). It runs in a namespace of its own, which its functions
keep as their globals, and the module a program sees gets only what `__all__` names; the classes
present themselves as C types (`present_native_class`: the module's name in `tp_name`, the names
table, final or not, the docstring). It is written from the C line by line, down to when things die:
two primitives (`_held_once`, `_tuple_set`) let a result tuple be recycled when nothing else holds
it, which is what keeps the last items alive until the next step.

A weak reference is an object with a record off to the side (`WeakRecord` in `object.hpp`, step 3c): the
header has no room for a list and few objects have one, so the flags `HAS_WEAKREFS` and `WEAK_REFERENCE`
say to look. Any object can hold the record, so `weakref.ref` (`runtime/prelude/_weakref.py`) is a class
of the prelude, with a subclass's storage from the object model. A proxy's attribute access is forwarded
by the runtime (`ClassObject::weak_proxy`), and everything else by its methods, as the C's slots do.
Which types have room is the names table's (`weakref:` rows, from `__weakrefoffset__`); a class has it as
it has a dict, unless `__slots__` leaves it out or the object has a variable size (an int's, where a
slot asks for it). A finaliser that leaves a count on its object stops the disposal (PEP 442), so an object
can die twice over: `release_attributes` says which. At exit the walk that stands for the collector
handles weak references as the collector does: one with a callback is cleared before any finaliser,
and its callback runs only if the walk did not reach the reference too.

A `frozendict` is a dict: `Kind::Dict`, the same table, views and iterators, with its own class and
the flag `FROZEN_DICT` (case C-6-11). What reads a dict therefore reads it, as CPython's `PyAnyDict`
paths do, and what writes one asks `is_dict` (`PyDict_Check`) or `is_exact_dict`, so a frozendict
falls through to the generic path and its TypeError. It is filled only while it is being made;
a subclass's instance is a `DictInstance` with the flag. `frozen_hash` is CPython's `ma_hash`.

An int outside the immediates is a `BigInt` (`Kind::BigInt`, class `int`), and a value that fits
an immediate is never one. `as_int` still answers only for an immediate's size, so that the fast
paths stay as they were; a path that takes every int asks `is_int` and reads through `IntView`
(an immediate, a bool, a `BigInt`, an `IntInstance` with limbs). An index has CPython's three
readings: `index_value` raises what the caller names ("cannot fit 'X' into an index-sized
integer"), `clipped_index` clips as a slice's bounds do, and `ssize_arg` and `c_int_arg` are a
clinic argument's, worded as `PyLong_AsSsize_t` and `PyLong_AsInt` word it. A `range` keeps four
machine words while they fit (rangeobject.c's fast case); otherwise four ints, and its iterator
is `longrange_iterator` exactly when CPython's is.

Still in C++ until the next step: the exception classes (the decision puts them in the prelude);
not yet anywhere: subclasses of `str`, `tuple`, `list` and the other C++ types (refused by name),
`bool` (final in CPython: refused here), `types.GenericAlias` (`dict[str, int]`), a class that overrides
`__getattribute__` or assigns `__class__` (refused as \[P2+\], spec section 3).

## 4. Building and running

`python3 pipeline/build.py --run prog.py args...` lowers the program and the modules it imports
(section 4a), compiles each at `-O1` under `build/compiled/units/` and links them with `libbella.a`,
which is the runtime sources and the compiled prelude at `-O2`, built once per content hash
(sources, prelude, the compiler's own Python, the flags) under a lock, so parallel builds share it.
The program's `main` is `run_main`: the builtins module and `sys`, the prelude modules (each runs
as the module it names; an `__all__` goes into builtins), the built-in modules' specs, then
`__main__`. At the end the modules' globals are released (section 4a), stdout is flushed, and an uncaught exception prints CPython's
report, the chain of causes and contexts first, each traceback with file and line (spec D-06),
the type by its qualified name and a `str()` that raises as `<exception str() failed>`
(RL-231, RL-250), and exits 1; a facility Bella lacks yet stops with
`bella: not implemented: ...` and exit 70, as the evaluators refuse.

## 4a. Imports (step 3b; case C-8-10, and C-8-01 and C-8-04 compiled)

A program is a closed world (spec section 8). `pipeline/closed_world.py` finds the modules it can
import from their import statements at build time, as CPython's import system would find them for
`python program.py`: a built-in or frozen module of the pinned interpreter first, then the
program's directory (`sys.path[0]`), a package before a module, a submodule in its parent's
directory, then the standard library as `closure.lock.json` knows it (`compiled`, or a shim whose
source is ours). The whole reachable closure is compiled (P-1): function-local imports count,
and an import that never runs costs only its compilation. What the runtime provides (`core`,
`mapped`) is not compiled, and the manifest's omissions behave as not installed. Each module is
emitted into a namespace of its own (`bella::mod_cycpkg_0a`), lowered once per content under
`build/compiled/lowered/` and compiled once under `build/compiled/units/`, keyed by its text, the
headers and the flags, so a change to the runtime's sources recompiles no unit. The standard
library's units compile at `-O0`, a fifth of the time, while speed is not a goal; the program's at
`-O1`. The main unit, generated last, holds `main()` and the registry (`ModuleEntry`) handed to
`run_main`. A kept example's C++ is its module's unit, without the main unit's absolute paths.
Generated names avoid the headers' macros (`ENOENT`, `S_IFMT`), which the compiler lists. Links strip
debug information (`BELLA_KEEP_DEBUG=1` keeps it), and a program rebuilt replaces its old binary.

The import system keeps CPython's split:
* `runtime/src/imports.cpp` is the C half: IMPORT_NAME (`_PyEval_LazyImportName`,
  `_PyEval_ImportName`), `builtins.__import__` (`PyImport_ImportModuleLevelObject`, `resolve_name`),
  IMPORT_FROM with each of its messages, `import *`, the module type (`__getattr__`, the messages of
  a partially initialised or shadowing module, `__repr__`, `__dir__`, `__dict__`, `ModuleType(...)`).
* `runtime/prelude/bootstrap.py` is `importlib._bootstrap`: CPython's own text for `_find_and_load`,
  `_load_unlocked`, `module_from_spec`, `_init_module_attrs`, `ModuleSpec`, `BuiltinImporter`,
  `FrozenImporter`, `_handle_fromlist` and `_module_repr`, unchanged except where a line says
  `bella:`. It runs as `_frozen_importlib`, so its classes say so. The closed world's registry
  stands for `sys.meta_path`'s finders; a source module's loader is a `SourceFileLoader` (of
  `_frozen_importlib_external`) whose `exec_module` runs the compiled body in the module's
  namespace, and the methods that read files are refused. A module CPython has frozen (`os`, `abc`)
  gets `FrozenImporter`'s spec and `<frozen os>` frames. With one thread a module lock is always
  this thread's own, so taking it waits for nothing. It has no frames, as importlib's are removed
  from tracebacks. It also holds `types.SimpleNamespace` (`namespaceobject.c`).
* A module the runtime provides is `BuiltinImporter`'s: `_types` so far, whose types without
  instances yet (a generator, a code object) exist as classes. The names table lists every attribute
  of the manifest's `core` and `mapped` built-in modules, so a name the runtime lacks is refused, not
  an AttributeError or an ImportError a program would take for the module's answer.

E-04 and E-06 exclude replacing `__import__` and writing `sys.modules` in a program's own code, and
the linter will say so; the runtime still behaves as CPython there, since the standard library
writes `sys.modules` (`os.path`, `collections.abc`). So `pipeline/tests/test_compiled_imports.py`
covers those paths, and case C-8-10 stays inside the dialect. What a hook alone could see of
CPython's C code importing `_io` to read a module's file has no counterpart here.

Lazy imports (PEP 810; C-8-05 to C-8-07) are
`Objects/lazyimportobject.c` and `import.c`'s lazy half, in `imports.cpp`. A `lazy_import` object is
a root (the absolute name, the fromlist, the builtins) or a projection (a placeholder and an
attribute, which IMPORT_FROM makes); it remembers its declaring frame's code and line, read from
the frame chain (`detail::FrameRecord`, which `globals()` reads too). A global, name or class-dict
load, a module's attribute (also its `__getattr__` and `__dir__`) and `resolve()` resolve it, and a
load writes the result back if the namespace still holds the placeholder. A plain `lazy import a.b`
binds the root package and leaves `b` pending on `a` (`lazy_pending_submodules`), so that `a.b`
imports it when read; `hasattr` and `getattr` with a default take `_Py_module_getattro_impl`'s
suppressing path (`optional_getattr`). A placeholder resolving itself raises `ImportCycleError`. A
resolution error keeps its chain and names the declaration: an `ImportError` as its cause with
a traceback entry, or, when it has a chain already, a note. No filter and no `lazy_imports` mode
exist (D-18, E-04), and `sys.lazy_modules` is left out, since a program could only read it (refused
by name); calling `__lazy_import__` outside module level is refused until `SyntaxError` exists.

What follows from that, each as CPython: a module's namespace starts with `module_init_dict`'s five
names, then `__path__`, `__file__`, `__builtins__` (the dict; `__main__`'s is the module); a module
enters `sys.modules` when its body starts, leaves it if the body fails, and moves to the end when it
finishes; a module run again after a failure is a new module object, whose functions read their
own run's namespace (`fn->module`: the emitter keeps no module pointer per unit, and makes a unit's
constants once); `globals()` is the innermost shown frame's module's (`FrameGuard` keeps it); an
AttributeError leaving `getattr` without `name` and `obj` gets them
(`set_attribute_error_context`). `ImportError` has `msg`, `name`, `path`, `name_from`, its keyword
arguments, `str` and `repr`.

At exit, on every way out but a refusal (a normal end, `sys.exit`, an uncaught exception after its
report), each module's globals are released in insertion order, the modules in `sys.modules` order
and then those it no longer holds, oldest first: `finalize_remove_modules` drops `sys.modules`'
entries in that order and a module whose last count goes releases its namespace (measured on
3.15.2; modules are immortal here, D-19, so only the namespaces are cleared, and D-07 leaves the
order open where a module is held by another or a traceback holds `__main__`). The status is
`_Py_HandleSystemExitAndKeyboardInterrupt`'s: a SystemExit's code, truncated to a C int.

Decided here, each stated where it matters:
* `sys.path` is `[the program's directory]` (D-18: it reflects the build): the other entries are the
  interpreter's search path, which a closed world does not have.
* `sys.modules` starts with `sys` and `builtins`, then `__main__`. CPython's start-up modules (`os`,
  `codecs`, `encodings`, `site`, ...) come when the runtime can run them at start-up, once their
  native modules exist; until then `'os' in sys.modules` before an import answers False where
  CPython answers True (open, in section 5).
* `__spec__.cached` is None and `cache_from_source` raises NotImplementedError, what CPython does
  with `sys.implementation.cache_tag` None (D-16): a compiled program has no bytecode cache.
* An ImportWarning has no effect while no `warnings` module is loaded: the default filters ignore
  it and nothing else can change them (`PYTHONWARNINGS` and `-W` are not read, D-18). Once one is
  loaded the warning is refused until warnings exist. A DeprecationWarning (`__package__ !=
  __spec__.parent`) is refused: the default filters show it in `__main__`.
* Importing a standard-library module the program does not have (`sys.stdlib_module_names`, in the
  names table: a native module not provided yet, a shim not written yet) is refused by name; a name
  found nowhere is ModuleNotFoundError when the import runs (C-8-04's `if False:` import never
  resolves). A namespace package is refused when imported.

`runtime/src/str.cpp` holds the str methods the import system needs first and the standard library
next (`find`, `split`, `partition`, `strip`, `replace` and their relatives), as `unicodeobject.c` and
`stringlib` do them: code-point indices, `ADJUST_INDICES`, `Py_UNICODE_ISSPACE`, each calling
convention's messages (an unexpected keyword is refused, since CPython's message may suggest one),
and the string itself where CPython returns it (`test_str_methods_are_cpythons`: each method on
nine strings and nine substrings with eight pairs of bounds, and each argument error).

## 5. Gaps, in the order the steps close them

* 3a.2, the rest: the exception classes into the prelude; subclasses of `str`, `tuple` and
  `list`; `types.GenericAlias`; the warnings machinery (a DeprecationWarning is refused where
  CPython would show one).
* The dict views' set operations and comparisons, `reversed` and `mapping`; `str %`
  formatting; `types.UnionType` (`int | str`).
* 3b, the standard library running: every module of a closure compiles, and what stops the corpus is
  now the native modules, by how many cases each stops: `_abc` 13, `_weakref` 5, `gc` 4, `_ast` 4,
  `_operator` 3, `itertools` 3, then one case each; and the builtins (`sorted`, `enumerate`, `zip`,
  `min`, `max`, ...), `str %`. `dir()` of names that are not all str
  waits for `list.sort`.
* CPython's start-up modules are not imported at start-up yet, so `sys.modules` shows them only once
  imported: a wrong answer for a program that asks before importing them, until they can run there.
* 3b: generators (state machines, design section 10.3): C-3-04.
* 3c: the cycle collector and weak references, model first: C-3-12, which closes task 3; with it,
  a caught exception keeps its frame's locals (RL-222, D-12).
* Lines: a frame's line is its statement's first line; CPython gives the failing instruction's,
  which differs inside a statement that spans lines (RL-225). The frontend and L2 would carry
  the expression positions; an inlined comprehension's line then goes to its caller's entry.
* `__notes__` in an uncaught exception's report (refused). The other exceptions' own fields
  (StopIteration's `value`) are refused by name, read, stored or deleted (RL-255), until those
  classes are built as CPython's.
* A `BigInt` holds its limbs in a `std::vector` and `bn` returns vectors, two allocations for each
  result, where the design has the limbs inline in the object. That is a speed matter and comes
  with the first measurement that asks; the numbers are the same.
* A class written in the prelude for a C type (`zip`, `itertools.chain`) is less than one in three ways
  no program should meet: its `__next__` is a function and not a slot wrapper, so its messages for
  wrong arguments are a function's; its slots' private names can be read; and
  `object.__new__(itertools.chain)` makes an empty one where CPython refuses.
* A request for an array of more than 2**40 words in `itertools` is a MemoryError at once: what the C
  would fail to allocate, the Python would first try to fill.
* Set operations and comparisons on `dict_keys` and `dict_items` and their `.mapping` are refused by
  name, for a frozendict's views as for a dict's. A container's `__repr__` is a function of the
  prelude, so `{}.__repr__(1)` says what a function says about its arguments, not what a slot
  wrapper says.
* Hashing nested frozendicts stops with RecursionError at a depth of 10000: CPython's limit there
  is the C stack, which no program can know.
* `1 << n` for `n` beyond 2**40 and a power of more than 2**40 bits are refused by name: where
  CPython has no such limit, memory decides, and it would answer with a MemoryError or a result.
* A constant CPython's compiler folds (`2**64`) is computed here at each evaluation, so `f() is f()`
  differs for it as for a tuple of constants; a literal is one object per module, as CPython's are.
* `_abc` holds classes where CPython holds weak references, until 3c (the author, 2026-11-04):
  `_get_dump` refuses a set with entries, and a metaclass's `__hash__` runs at each look-up where
  CPython's reference keeps the first answer. `__abc_tpflags__` is taken and checked, and its bits
  have no reader until `match` is compiled, when subclasses inherit them and `register` passes
  them on.
* `type.__subclasses__` of a built-in type is refused: CPython's list names classes of its own.
* `enumerate`, `zip`, `map`, `filter` and `reversed` are written in Python (`runtime/prelude/iterating.py`):
  their `__reduce__` stops by name, `dir()` shows CPython's names, and `reversed` of a dict stops by name
  (`dict.__reversed__`). `sum` keeps `builtin_sum_impl`'s stages, since which of them an item ends decides how a
  later float is rounded: exact ints in a C long, then floats compensated with ints in a C long among them, then `+`.
* `float` (`runtime/src/float.cpp`, C-6-12): the object is a double, and a subclass's instance adds an attribute
  storage as `IntInstance` does. The digits are libstdc++'s (`make float-diff`), and everything around them is the C's.
  What is not finished: a negative float to a fractional power stops by name until `complex`; `float()` of a str
  beyond ASCII stops by name until the Unicode database; `format` with a specification stops by name for every type.
* `bytes` and `bytearray`: `%`, a class derived from them, the codecs UTF-16 and UTF-32 and the
  `namereplace` handler stop by name; `codecs.register_error` has nothing to register with until
  `_codecs` is written. `memoryview` and the buffer protocol are \[P2+\].
* A tuple of constants is built where it is evaluated: `f() is f()` for `def f(): return (1, 'a')` is
  True under CPython, which folds it into one constant, and False here.
* `types.GenericAlias` is written in Python (`bootstrap.py`), so `vars(types.GenericAlias)` shows a
  `__setattr__`, `__delattr__`, `__reduce_ex__` and a slot `_ga_parameters` CPython's lacks, and its
  methods are functions, where CPython's are slot wrappers and method descriptors. `X | Y` with an
  alias is refused until `types.UnionType` exists.
* `object.__getattribute__` of a class, or of an object whose class has `__getattr__`, is refused:
  the instances' path runs the hook and cannot yet skip it.
* `dir()` and `__dir__` list a built-in type's names from the table of CPython's, so `dir(x)` is
  exact; a direct `x.__dir__()` has them in the table's order, which `dir()` sorts away. A class's
  `__weakref__` is listed though its dict lacks it (RL-323).
* A class's `__dict__` is not a dict: the first view (`keys`, `values`, `items`, `iter`, `copy`)
  makes one that follows the class (`ClassObject::dict_view`, `RefClass.class_dict`). Set operations
  on views and comparing them stay refused for every dict.
* At exit a walk from the namespaces stands for the collector (RL-281), until 3c. Until then a
  finaliser on an object no namespace reaches does not run, and no class has `__weakref__` in its
  `__dict__` (RL-323). A special method CPython's built-in type has of its own and
  `runtime/src/slots.cpp` lacks is refused where it is read (RL-310); so is a built-in method's
  docstring (RL-279).
* `__suppress_context__` and super's `__thisclass__`, `__self__`, `__self_class__` present as
  `getset_descriptor`s, CPython's as `member_descriptor`s, whose type the runtime has, without
  methods (RL-251, RL-254).
* `super()` in a function that deletes its first argument is refused at build (RL-319; CPython:
  `RuntimeError: super(): arg[0] deleted`); under `eval1` it raises UnboundLocalError (task 4, A3's
  known edges).
* Later: the slot wrappers' own types (`wrapper_descriptor`, `method-wrapper`), whose repr and
  type are refused today (RL-218); the names RL-211's table refuses, as programs need them.
* Later: `format` specifications, the global read caches of decision 6, the Unicode database
  for `repr` beyond Latin-1, the rest of the builtins.
* Speed is not a goal yet: everything is boxed and every call binds generically, so the compiled
  `fib` takes about twice CPython's time. Phase 2's types change that.
