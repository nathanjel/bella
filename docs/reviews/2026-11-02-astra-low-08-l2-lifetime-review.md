# L2 Lifetime Review

Date: 2026-11-02

Reviewer: astra-low

Sequence: 08

Reviewed range: `58bb34b7b6b2fdce87e2972b87f38c80cbc0aa7a..d28b25606840edeed5ccdcae4d1207b3c2773634`

Reviewed HEAD: `d28b25606840edeed5ccdcae4d1207b3c2773634`

The explicit L2 representation and the model/header differential are useful foundations. The new evidence does not yet establish exact lifetimes: I reproduced ten execution or lowering mismatches, including a heap use-after-free in the header, plus one checker counterexample. The most consequential gaps are ownership across callbacks, references retained by helper tracebacks, and treating symbol-table discovery order as frame-slot order. These should be resolved before the emitter treats L2 and the object header as trusted specifications.

The implementation choices for big integers, float digits, libm and boxed L2 remain reasonable within the author's recorded decisions. This range supplies a float-digit differential, not the completed Python float wrapper or bigint implementation. My local float results support the narrower digit claim. I have not audited SEL's source or settled the explicitly open L-09/L-10 licence entries.

## Verification

The tree was clean at the requested endpoint. I ran:

```sh
uv run python --version
uv run make test eval2-corpus targets-eval2 object-test float-diff
```

The interpreter reported **Python 3.15.2** and the full make command exited zero:

- 180 tests passed, including the prior-review regressions; reference-model selftest passed 3,000 operations over 50 worlds.
- eval2 preserved its 63-case baseline out of 76 cases.
- All three easy targets matched their recordings with their full closures under eval2.
- The header differential passed 3,000 operations, 199 deaths and 63,897 cache hits; ASan/UBSan passed 1,020 operations and 70 deaths.
- Float differential: 375,024 shortest, 150,000 scientific, 150,000 fixed and 225,007 parse cases, with zero unexpected differences. There were 2,560 out-of-range parses delegated to the future wrapper.

Additional programs below were run in separate processes on that pinned interpreter and the supplied eval2 runner. Header probes used the local GCC **16.2.1**, including ASan/UBSan. I did not rebuild Docker or independently inspect GitHub CI. The requested tests' success and the separate ASan failure below are both reproducible: the random world's descriptors do not exercise the callback mutation in A8-1, and its checking mode also quarantines dead storage.

Only this review file is added. No implementation, expectation, decision or review-log entry is changed. A8 identifiers are local to this review. The stated exclusions—comprehension/PEP 695 scope differences, async bodies, model resurrection/threads/weakrefs/class freeing and the remaining emitter work—are not findings here.

All commands below run from the repository root. Save each code block under the filename given in its command. Unless stated otherwise, both processes exit zero and the output blocks are stdout.

## A8-1 — High: a lookup's borrowed fallback hook can be freed before it is called

Locations: `runtime/include/bella/object.hpp:590`, especially `:600` and `:610`; `call` at `:435`.

CPython reproduction, saved as `/tmp/a8_hook.py`:

```python
class D:
    def __get__(self, obj, cls):
        del cls.__getattr__
        raise AttributeError('x')
class C:
    x = D()
    def __getattr__(self, name): return 7
print(C().x)
```

```sh
uv run python /tmp/a8_hook.py
uv run python pipeline/l2/run.py /tmp/a8_hook.py
```

Both print `7`; host objects conceal the header defect. The equivalent header program, `/tmp/a8_hook.cpp`, is:

```cpp
#include "bella/object.hpp"
#include <iostream>
using namespace bella;
int main() {
    auto* c = make_class({.name="C"});
    auto* hook = new Function([](std::span<const Obj>) { return Obj::small(7); });
    c->set_attr(intern("__getattr__"), Obj::of(hook));
    auto* get = new Function([c](std::span<const Obj>) -> Obj {
        c->del_attr(intern("__getattr__"));
        throw AttributeError("x");
    });
    auto* d = make_class({.name="D", .attrs={{"__get__", Obj::of(get)}}});
    c->set_attr(intern("x"), Obj::of(new_instance(d)));
    Ref obj = Ref::share(Obj::of(new_instance(c)));
    std::cout << getattr(static_cast<Instance*>(obj.get().object()), intern("x"))
                     .get().small_value() << '\n';
}
```

```sh
g++ -std=c++26 -O1 -g -fsanitize=address,undefined -fno-omit-frame-pointer \
    -Iruntime/include /tmp/a8_hook.cpp -o /tmp/a8_hook
ASAN_OPTIONS=detect_leaks=0 /tmp/a8_hook
```

Bella aborts with ASan `heap-use-after-free`: the read is in `bella::call` at `object.hpp:435`, reached from `execute` at `:610`. The free comes from `ClassObject::del_attr` at `:299` during the descriptor callback. Addresses and build paths are omitted here; the object and access are not ambiguous.

Class-version invalidation does happen before the release. That protects a subsequent cache lookup, but the current `LookupPlan` already contains the borrowed hook. Revalidating a cache does not protect an operation in progress, and replacing the hook by a fresh lookup would also be wrong: CPython calls the previously selected hook.

Suggested fix: establish owning execution references before invoking user code, including the selected fallback and descriptor/callable where required. Keep cache entries borrowed. Measure when those execution references are released, and add reentrant descriptor/hook mutations to the model and header differential, including a run without quarantine.

## A8-2 — High: helper tracebacks retain operands beyond exception unwinding

Locations: `pipeline/l2/eval2.py:157`, `:161`, `:173`, and `:494`.

Save as `/tmp/a8_error_release.py`:

```python
class O:
    def __del__(self): print('del arg')
try:
    x = 1
    x += O()
except TypeError:
    print('handler')
print('after')
```

```sh
uv run python /tmp/a8_error_release.py
uv run python pipeline/l2/run.py /tmp/a8_error_release.py
```

CPython:

```text
del arg
handler
after
```

Bella:

```text
handler
del arg
after
```

`_Runtime.inplace` leaves its `a`/`b` parameters in a traceback frame when `operator.iadd` raises. Clearing the generated `_l2_t*` locals cannot clear these additional owners. This is not the legitimate retention of a program function's locals by its traceback: no Python-defined arithmetic method exists in this example.

Also reproduced with failed unpacking (`a, b = [O()]`), a non-iterable sole star argument, and non-mapping `**` arguments. Some helper paths leave cycles and defer destruction beyond the handler altogether. Running this arithmetic probe through `Interpreter(audit=True)` still prints Bella's order and completes without `AuditError`.

Suggested fix: remove or clear only implementation-owned traceback frames/references on every exceptional operation boundary, preserving the program's real frames and exception relationships. Exercise exception edges in the release audit. `docs/l2.md:194` currently says eval2 cuts its own frames out; the implementation's unwind only overwrites generated temporaries and does not fulfil that claim.

## A8-3 — High: failed `with` entry leaves synthetic owners alive

Location: `pipeline/l1/frontend.py:1445` (`_With._expand`, initialization before the cleanup region).

Save as `/tmp/a8_with_entry.py`:

```python
class C:
    def __enter__(self): raise ValueError('bad')
    def __exit__(self, *args): pass
    def __del__(self): print('del manager')
try:
    with C(): pass
except ValueError:
    print('handler')
print('after')
```

```sh
uv run python /tmp/a8_with_entry.py
uv run python pipeline/l2/run.py /tmp/a8_with_entry.py
```

CPython:

```text
handler
del manager
after
```

Bella:

```text
handler
after
del manager
```

The normal-path deletes added in this range do not cover an exception from `__enter__`. The synthetic bound `__enter__` and `__exit__` locals survive; generated exception unwinding clears L2 temporaries, not these L1 synthetic locals. CPython legitimately keeps `self` through the exception handler's traceback, then releases it; Bella keeps additional references after that.

A failed assignment of the entered value has a related hole: with `__enter__` returning a non-iterable finalizable object and `with C() as (a, b)`, CPython destroys that value before calling a suppressing `__exit__`; Bella keeps `_val*` until after the statement. This path also encounters A8-2's unpack helper, so both ownership layers need attention.

Suggested fix: cover method lookup, entry and target assignment with cleanup regions matching their actual stack ownership, while still never invoking `__exit__` when `__enter__` fails. Add failure probes as well as the existing successful-manager probe.

## A8-4 — Medium: chained comparisons leave the middle operand in a hidden local

Locations: `pipeline/l1/frontend.py:1391`, `pipeline/l2/resolve.py:266`, `pipeline/l2/lower.py:389`.

Save as `/tmp/a8_chain.py`:

```python
class C:
    def __init__(self, n): self.n = n
    def __lt__(self, other): return True
    def __del__(self): print('del', self.n)
print(C('a') < C('b') < C('c'))
print('after')
```

```sh
uv run python /tmp/a8_chain.py
uv run python pipeline/l2/run.py /tmp/a8_chain.py
```

CPython:

```text
del a
del c
del b
True
after
```

Bella:

```text
del a
del c
True
after
del b
```

The walrus introduced for the middle operand becomes a synthetic local. L2 correctly releases its own operand temporaries but never deletes that local after the chain. This does not involve the explicitly accepted comprehension or PEP 695 scope differences.

Suggested fix: lower comparison-chain intermediates into lifetime-managed expression values, or give the synthetic binding explicit cleanup on the success, short-circuit and exception paths. Hiding a name from `locals()` does not hide its ownership.

## A8-5 — High: annotation-only declarations give locals the wrong slot order

Locations: `pipeline/l2/resolve.py:159`, `:333`; the generated dead declarations at `pipeline/l2/eval2.py:440` preserve the erroneous order.

Save as `/tmp/a8_slots.py`:

```python
class O:
    def __init__(self, n): self.n = n
    def __del__(self): print(self.n)
def f():
    z: int
    a = O('a')
    z = O('z')
f()
```

```sh
uv run python /tmp/a8_slots.py
uv run python pipeline/l2/run.py /tmp/a8_slots.py
```

CPython prints `z` then `a`; Bella prints `a` then `z`.

Measured separately with the repository's `pipeline.tests.test_l2_resolve.differences(Path('/tmp/a8_slots.py'))`: CPython's `f.co_varnames` is `('a', 'z')`, while resolve-names produces `('z', 'a')`; both cell/free tables are empty. The annotation establishes a local binding but does not allocate its fast-local slot at that statement. `_slots` currently uses the collector's first-seen order for both jobs.

Suggested fix: separate symbol classification from code-generation slot allocation and measure annotation-only/read/delete/dead-code cases. The generated host code's slot check cannot independently catch this defect: it starts with artificial assignments specifically arranged in L2's requested order, and therefore agrees with the wrong table.

## A8-6 — High: an intermediate `global` declaration fails to block closure capture

Location: `pipeline/l2/resolve.py:289` (`_analyze` child bound-set construction).

Save as `/tmp/a8_global.py`:

```python
x = 1
def outer():
    x = 2
    def middle():
        global x
        def inner(): return x
        return inner
    return middle()
print(outer()())
```

```sh
uv run python /tmp/a8_global.py
uv run python pipeline/l2/run.py /tmp/a8_global.py
```

CPython prints `1`, exit zero. Bella produces no stdout and exits 1 during lowering. Its traceback ends:

```text
KeyError: "to-anf: outer.<locals>.middle has no cell for 'x' to pass on"
```

`middle` classifies its own `x` as global but passes the enclosing function's binding of `x` into the child analysis unchanged. `inner` consequently asks for a closure cell that `middle` does not have.

Suggested fix: carry explicit-global scope barriers through recursive analysis rather than just accumulating enclosing bound names. Test a declaration between a binding and multiple nested functions, including cases where a deeper function introduces a new local binding of its own.

## A8-7 — High: aliases and expanded calls bypass namespace hygiene

Location: `pipeline/l2/eval2.py:379`, especially the name-based test at `:382` and untreated `CallEx` at `:388`.

Save as `/tmp/a8_locals.py`:

```python
def f():
    see = locals
    print('_l2_R' in see())
    print('_l2_R' in locals(*()))
f()
```

```sh
uv run python /tmp/a8_locals.py
uv run python pipeline/l2/run.py /tmp/a8_locals.py
```

CPython prints `False` twice; Bella prints `True` twice. Both calls expose the actual generated frame, including temporary references and the runtime helper. A `vars` alias reproduces the same problem.

The interception depends on the syntactic loaded name and only covers `G.Call`. The callable's identity and its need for the program's namespace do not change when it is assigned to another variable or invoked with an empty star expansion. A returned locals snapshot can also keep the leaked temporaries alive, so this is more than a cosmetic namespace difference.

Suggested fix: handle frame-sensitive builtins by callable identity on every invocation path, including `CallEx`, aliases and attribute loads. Preserve the originating program frame when doing so. Apply that audit to the same dispatch's staged `exec`/`eval`/`compile` paths; their staging and namespace checks should not depend on a particular spelling of the callee.

## A8-8 — High: generated exception handlers resolve the program's `BaseException`

Locations: `pipeline/l2/eval2.py:468`, `:618`, `:625`.

Save as `/tmp/a8_shadow.py`:

```python
BaseException = int
try:
    1 / 0
except ZeroDivisionError:
    print('caught')
```

```sh
uv run python /tmp/a8_shadow.py
uv run python pipeline/l2/run.py /tmp/a8_shadow.py
```

CPython prints `caught`, exit zero. Bella has no stdout, exits 1, and reports:

```text
TypeError: catching classes that do not inherit from BaseException is not allowed
```

The translator inserts bare `except BaseException` clauses into functions whose globals deliberately are the program's globals. Consequently, ordinary legal builtin shadowing changes implementation cleanup and dispatch. The original program's handler never mentions `BaseException`.

Suggested fix: capture the actual builtin exception root through the reserved implementation environment, and use that binding for generated handlers. Keep program-written exception expressions resolved normally. Check the frontend's generated `with` handler for the same distinction.

## A8-9 — Medium: valid unreachable source becomes a wf2 error

Locations: `pipeline/l2/lower.py:173`; `pipeline/l2/wf.py:118`.

Save as `/tmp/a8_dead.py`:

```python
def f():
    return 1
    x = 2
print(f())
```

```sh
uv run python /tmp/a8_dead.py
uv run python pipeline/l2/run.py /tmp/a8_dead.py
```

CPython prints `1`. Bella exits 70 without stdout:

```text
bella-eval2: unsupported: f: unreachable statement Line
```

The lowerer emits statements after a terminator, and neither it nor lifetimes removes them before wf2 rejects them. This is ordinary unreachable Python, not D-10's prohibited control transfer out of a `finally` block.

Suggested fix: collect the complete source's binding information first, then omit unreachable executable L2 statements, or explicitly support dead blocks in wf2. Simply skipping the source before resolution would lose bindings that still affect Python's scope classification.

## A8-10 — Medium: model and header release slots in declaration order instead of CPython's order

Locations: `refmodel/objects.py:368`, `runtime/include/bella/object.hpp:828`; the incorrect rule also appears in `docs/DECISIONS.md:541` and the model/header docstrings.

CPython program, `/tmp/a8_slot_death.py`:

```python
class O:
    def __init__(self, n): self.n = n
    def __del__(self): print(self.n)
class C:
    __slots__ = ('z', 'a')
c = C()
c.a = O('a')
c.z = O('z')
del c
```

```sh
uv run python /tmp/a8_slot_death.py
```

CPython prints `a` then `z`. Eval2 agrees because it uses host classes. The model program, `/tmp/a8_slot_model.py`, is:

```python
from refmodel.objects import RefClass, RefObject, Runtime, Heap, incref, decref
h = Heap()
rt = Runtime()
c = RefClass('C', slots=('z', 'a'), heap=h)
t = RefClass('T', heap=h)
o = RefObject(c)
incref(o)
rt.setattr(o, 'a', RefObject(t, tag='a'))
rt.setattr(o, 'z', RefObject(t, tag='z'))
decref(o)
print(h.deaths)
```

```sh
PYTHONPATH=. uv run python /tmp/a8_slot_model.py
```

Bella's model prints `['z', 'a']`. The equivalent header probe, `/tmp/a8_slot_header.cpp`, is:

```cpp
#include "bella/object.hpp"
#include <iostream>
using namespace bella;
int main() {
    auto* c = make_class({.name="C", .slots=std::vector<std::string>{"z", "a"}});
    auto* t = make_class({.name="T"});
    heap().on_death = [](Object* o) {
        auto tag = static_cast<Instance*>(o)->tag;
        if (tag >= 0) std::cout << (tag == 1 ? "a\n" : "z\n");
    };
    Ref obj = Ref::share(Obj::of(new_instance(c)));
    auto* a = new_instance(t); a->tag = 1;
    auto* z = new_instance(t); z->tag = 2;
    setattr(static_cast<Instance*>(obj.get().object()), intern("a"), Obj::of(a));
    setattr(static_cast<Instance*>(obj.get().object()), intern("z"), Obj::of(z));
}
```

```sh
g++ -std=c++26 -O1 -Iruntime/include /tmp/a8_slot_header.cpp -o /tmp/a8_slot_header
/tmp/a8_slot_header
```

The header prints `z` then `a`, matching the model's wrong order. This example has two string slots, no resurrection, no weak references, no override and no shared-key limit issue.

Suggested fix: derive per-class slot storage/deallocation order from CPython's processed slot names rather than the original declaration tuple. Retain the most-derived-class-first rule separately. Add deliberately unsorted and mangled slot names to the three-way tests and correct the recorded declaration-order claim.

## A8-11 — Medium: wf2 checks `finally` against the pre-try live set after a consuming return

Location: `pipeline/l2/wf.py:253`.

This is a malformed-L2 counterexample, not a Python-source behavior comparison: CPython has no public L2 temporary checker. The expected result follows from the declared L2 contract that `Return(t)` consumes `t` and a consumed temporary cannot subsequently be used.

Save as `/tmp/a8_wf.py`:

```python
from pipeline.l2 import grammar as G
from pipeline.l2.wf import check
from pipeline.l2.eval2 import Interpreter

v, f = G.Temp(1), G.Temp(2)
fn = G.Code('f', 'f', 'function', (), (), (), (), (
    G.Let(v, G.Copy(G.Const('value'))),
    G.Try((G.Return(v),), finalbody=(
        G.Let(f, G.Load(G.NameRef('global', 'print'))),
        G.Do(G.Call(f, (v,))),
        G.Release(f),
    )),
))
module = G.Module(G.Code('<module>', '<module>', 'module', (), (), (), (), (
    G.Let(f, G.MakeFunction(fn)),
    G.Do(G.Call(f, ())),
    G.Release(f),
)))
check(module)
print('accepted')
Interpreter().run_module(module)
```

```sh
PYTHONPATH=. uv run python /tmp/a8_wf.py
```

Actual Bella output:

```text
accepted
value
```

The return path consumes `t1`, but `finally` is checked with the entry set that still contains it. Eval2 also leaves the host temporary intact on return, masking the checker hole. This does not demonstrate the current lowerer generating that malformed program; it refutes the stronger checker guarantee independently.

Suggested fix: propagate the live state of each normal and abrupt exit through `finally`, with pending return ownership represented separately. If the intended rule instead defers consumption until after `finally`, specify that explicitly and make the checker, evaluator and future emitter use that same rule. The current consuming-Return contract and the accepted program disagree.

## Implications for the next increment

The existing successes establish useful ordinary-path coverage. They should remain regression gates, supplemented by callbacks that mutate the structures owning them, exceptional protocol operations, and tiny source-to-slot-table differentials. In particular, RL-20's cache invariant can hold while an execution plan still has a dangling borrowed value; checking generated host slots against intentionally ordered generated declarations can agree with an incorrect source table; and auditing explicit `Release` statements misses owners retained during exception unwinding.

The spec's exact finalization requirement and the documented whole-program compilation approach need no relaxation to fix these examples. The next pass should make the implementations and their evidence meet those claims. The documented native/backend gaps remain separate from these failures in the already implemented L2 and object-model paths.
