Codex `gpt-6.2-astra` at low reasoning effort, 2026-11-21, the cross-check the author asked for after each step. Verbatim. Tag A29 in the
review log. Its range is `2977264..b04274c`, four commits, run non-interactively (standard input closed) in its own worktree (`bella-r29`) at
`b04274c`: the native stack (RL-624, C-8-20) first, then the sweep of a type's slots (RL-621) and the fixes of A28. Its probes
(`r29-probes/codex/`) stayed in that worktree. Ten findings; each program was run on both sides by the session before any verdict (review
log, A29).

---

# A29 · Bella conformance review

Detached b04274c, range 2977264..b04274c. All measured rows ran in their own process with PYTHONHASHSEED=0, 120 seconds, an 8192 KiB stack and an 8000000 KiB virtual-memory limit unless specified. Builds used `timeout 600 ./r29-build path/to/prog.py`. The [runner](r29-probes/codex/run) invokes the printed binary or `.venv/bin/python path/to/prog.py` with the same row argument. Each row directory holds the six raw stream and status files. Reduced examples below show the relevant operation from the executed probe. All four findings below have empty stderr and exit status 0 on both sides.

## A29-01 · Medium · CSV writes a nonnumber unquoted

`runtime/prelude/_csv.py:463`. The numeric-field check reads attributes of the class object, letting its metaclass supply a nonexistent numeric slot. A consumer using QUOTE_NONNUMERIC would attempt to convert the resulting bare word to a float. [Executed program](r29-probes/codex/dispatch/prog.py) · [csv row](r29-probes/codex/dispatch/csv)

```python
import csv, io
class Meta(type):
    def __getattr__(cls, name):
        if name == "__index__":
            print("lookup", name)
            return lambda x: 17
        raise AttributeError(name)
class Fake(metaclass=Meta):
    def __str__(self): return "field"
s = io.StringIO()
csv.writer(s, quoting=csv.QUOTE_NONNUMERIC).writerow([Fake()])
print(repr(s.getvalue()))
```

CPython stdout is `'"field"\r\n'`. Bella prints `lookup __index__` followed by `'field\r\n'` on the next line.

## A29-02 · Medium · math accepts a method supplied by the metaclass

`runtime/prelude/math.py:507`. With the same metaclass pattern, replace the tested name with `__ceil__`, and run the following. CPython's special-method lookup finds no method. Bella's ordinary class lookup invokes the hook. The floor and trunc rows give the corresponding results with their own method names. [Executed program](r29-probes/codex/dispatch/prog.py) · [ceil row](r29-probes/codex/dispatch/ceil)

```python
import math
try: print(math.ceil(Fake()))
except Exception as e: print(type(e).__name__)
```

CPython prints `TypeError`. Bella prints `lookup __ceil__` and `17` on successive lines.

## A29-03 · Medium · math passes an extra argument to a static special method

`runtime/prelude/math.py:510`. After class lookup the helper calls the result with the instance. A staticmethod already produces the callable that CPython invokes with zero arguments. This also needs fixing if the metaclass lookup in A29-02 is corrected. [static row](r29-probes/codex/dispatch/static)

```python
import math
class Static:
    __ceil__ = staticmethod(lambda: 17)
try: print(math.ceil(Static()))
except Exception as e: print(type(e).__name__)
```

CPython prints `17`. Bella prints `TypeError`.

## A29-04 · Low · operator.length_hint invokes an observable metaclass hook

`runtime/prelude/_operator.py:273`. Once special lookup has found no length hint, a second lookup on the type runs user code before returning the default. Use A29-01's metaclass with the tested name replaced by `__length_hint__`, then run `import operator; print(operator.length_hint(Fake(), 23))`. CPython prints only `23`. Bella prints `lookup __length_hint__` then `23`. [hint row](r29-probes/codex/dispatch/hint)

## A29-05 · Medium · A list comprehension consumes a recursion-limit entry

`pipeline/l1/frontend.py:1819` creates a helper function for the comprehension. Its call consumes a recursion entry on every descent. CPython 3.15 inlines this comprehension. [Executed program](r29-probes/codex/recursion/prog.py) · [comp-50](r29-probes/codex/recursion/comp-50)

```python
import sys
sys.setrecursionlimit(50)
n = 0
def f():
    global n
    n += 1
    return [f() for i in [0]]
try: f()
except RecursionError: print(n)
```

The probe prints the limit, counts user-function entries, catches the exception, and repeats. CPython stdout at 50 is `50\n49\n49\n`. Bella gives `50\n25\n25\n`. Both exit 0 with empty stderr. At limits 200, 1000 and 3000 the counts per attempt are respectively 199, 999, 2999 for CPython and 100, 500, 1500 for Bella.

## A29-06 · Medium · Recursive callbacks lose half their Python recursion budget

`runtime/src/call.cpp:2547` counts compiled prelude frames. The property descriptor (`runtime/prelude/builtins.py:387`), map iterator (`runtime/prelude/iterating.py:362`) and reduce implementation (`runtime/prelude/_functools.py:420`) keep a counted frame while calling user code. CPython implements these operations in C. The discrepancy follows the configured limit even at 50. [prop-50](r29-probes/codex/recursion/prop-50) · [map-50](r29-probes/codex/recursion/map-50) · [reduce-50](r29-probes/codex/recursion/reduce-50)

```python
import sys
sys.setrecursionlimit(50)
n = 0
class X:
    @property
    def p(self):
        global n
        n += 1
        return self.p
try: X().p
except RecursionError: print(n)
```

At limit 50 the executed property row prints `50\n49\n49\n` on CPython and `50\n24\n24\n` on Bella. The map and reduce rows each print `50\n49\n49\n` on CPython and `50\n25\n25\n` on Bella. All exit 0 with empty stderr. At 200, 1000 and 3000, Bella records 99, 499 and 1499 property getters, or 100, 500 and 1500 map/reduce callback entries. CPython records 199, 999 and 2999 in each case.

## A29-07 · Low · A literal warning-path marker collides with a real path in the harness

`conformance/harness.py:195` substitutes a string that a program can also write literally. This is a false-equality case in the test oracle. The binaries agree on each individual input. [Program](r29-probes/codex/mask/prog.py) · [real path](r29-probes/codex/mask/real) · [literal marker](r29-probes/codex/mask/literal)

```python
import sys
print(sys.argv[1] + "/demo.py:7: phase: done: trailing text", file=sys.stderr)
```

Both interpreters ran with both arguments under the limits above. With the actual cases directory, CPython stderr is `/home/nathan/workspaces/nth/bella-r29/conformance/cases/demo.py:7: phase: done: trailing text` plus newline. With literal argument `<cases>`, Bella stderr is `<cases>/demo.py:7: phase: done: trailing text` plus newline. Both runs have empty stdout and exit 0. Passing each captured stream to the checkout's actual `mask_stderr` yields the second string including the newline in both cases. The suffix is preserved.

## A29-08 · Medium · bindtextdomain converts a path through the wrong receiver

`runtime/prelude/_locale.py:239` fetches `__fspath__` by ordinary class attribute lookup, then calls it with the path object. CPython's filesystem conversion looks up the special method on the path object's type and calls the bound result. Both parts of the difference are observable. [Executed program](r29-probes/codex/path/prog.py) · [meta](r29-probes/codex/path/meta) · [static](r29-probes/codex/path/static)

```python
import _locale
class Static:
    __fspath__ = staticmethod(lambda: "/tmp")
try: print(_locale.bindtextdomain("bella-a29-example", Static()))
except Exception as e: print(type(e).__name__)
```

CPython prints `/tmp`. Bella prints `TypeError`. In the metaclass row, only the metaclass supplies the method. CPython prints `TypeError`. Bella prints `lookup __fspath__` then `/tmp`. Each run exits 0 with empty stderr.

## A29-09 · Medium · Class construction asks a namespace's metaclass whether it is a mapping

`runtime/prelude/build_class.py:84`. The mapping check after `__prepare__` reads `__getitem__` as a class attribute and tests it against None. CPython checks the presence of the mapping slot. A meta-only method lets Bella enter the class body with a nonmapping, and a class method set to None makes Bella reject the namespace too early. [Executed program](r29-probes/codex/prepare/prog.py) · [meta](r29-probes/codex/prepare/meta) · [none](r29-probes/codex/prepare/none)

```python
class M(type):
    def __getattr__(cls, name):
        if name == "__getitem__":
            print("lookup", name)
            return lambda *args: 1
        raise AttributeError(name)
class Fake(metaclass=M): pass
class Make(type):
    @classmethod
    def __prepare__(cls, name, bases): return Fake()
try:
    class T(metaclass=Make): pass
except Exception as e: print(type(e).__name__, str(e))
```

CPython prints `TypeError Make.__prepare__() must return a mapping, not Fake`. Bella prints `lookup __getitem__` followed by `TypeError 'Fake' object is not subscriptable`. Returning an instance of `class NoCall: __getitem__ = None` instead gives `TypeError 'NoneType' object is not callable` on CPython and `TypeError Make.__prepare__() must return a mapping, not NoCall` on Bella. All runs exit 0 with empty stderr.

## A29-10 · Medium · Built-in data walks can raise solely because of the Python recursion limit

At depth 100 and a Python recursion limit of 50, a program with no recursive Python function can lose a successful operation. The list representation (`runtime/prelude/builtins.py:654`), deque element comparison (`runtime/prelude/_collections.py:310`) and JSON accelerator (`runtime/prelude/_json.py:690`) recurse through compiled Python helpers. Their frame entries debit the Python budget at `runtime/src/call.cpp:2547`. The corresponding CPython operations walk this data in C. [Executed program](r29-probes/codex/walk-supported/prog.py) · [repr](r29-probes/codex/walk-supported/list-repr) · [comparison](r29-probes/codex/walk-supported/queue-eq) · [JSON](r29-probes/codex/walk-supported/list-json)

```python
import sys
x = 0
for _ in range(100): x = [x]
sys.setrecursionlimit(50)
try:
    repr(x)
    print("done")
except RecursionError: print("RecursionError")
sys.setrecursionlimit(1000)
del x
print("continued")
```

Under a 1024 KiB stack CPython prints `done\ncontinued\n` and Bella prints `RecursionError\ncontinued\n`; both exit 0 with empty stderr. The same outcomes were measured for these operations:

- `repr` and `str` of lists, tuples, a tuple subclass, dicts, deques, OrderedDicts, defaultdicts, SimpleNamespaces and partials.
- Formatting the nested list with `format`, an f-string, `%r`, `str.format` or `ascii`, and encoding it with `json.dumps`.
- Comparing two distinct but equal nested deques with `operator.eq`, `!=` or `<`. The discrepancy also appears through membership, index, count and remove on an outer list, and through sorted, min and max.

An 8192 KiB stack gave the same discrepancy for list repr, deque equality and JSON with the limit still at 50. [Stack controls](r29-probes/codex/walk-control)

The set and frozenset representation rows also differ with the same two stdout streams. They contain 100 alternating frozenset and tuple layers. With the original 1024 KiB stack, raising the Python limit to 1000 made both the list repr and deque comparison succeed in Bella. JSON still raised under that combination, and succeeded at 8192 KiB and limit 1000. Thus both resource settings matter for the JSON example. [Set rows](r29-probes/codex/frozen) · [Limit controls](r29-probes/codex/walk-limit-control) · [JSON control](r29-probes/codex/walk-both-controls/list-json)

## Coverage limits

The 200,000-level measurements below cover operations that read only an outer layer or explicitly iterate down the structure. The review did not exercise crash, hang or memory-exhaustion reproductions. It does not establish an abnormal-termination result for the requested extreme-depth release and recursive-walk matrix. The attempted frozen dataclass program stopped by name before its operation; the other bounded walks were rebuilt without it. Instance `__getattribute__` overrides are outside the supported group. The separately listed finalization and shutdown exclusions were applied, including RL-222 and RL-514. The program-exit chain probe observed process completion only.

## Checks that agreed

- **Destruction.** All 10,000 finalizer and weak-callback events matched byte for byte in the 5,000-node row. The 5- and 50-node rows also matched. At those smaller sizes the comparisons covered a dict-backed node, a node with a slot and inherited dict, and links through deque, OrderedDict, defaultdict, partial, bound method, closure cell, suspended generator, iter, map, filter, zip, SimpleNamespace, named tuple, list subclass and tuple subclass. Resurrecting the middle node at depth 50 gave the same surviving weak references and complete event sequence after release. [Lifetime probes](r29-probes/codex/lifetime)
- **Other owners and release sites.** All 15 release rows matched, including pure slotted nodes, dict keys and values, set members, itertools.chain, exception cause/context holders, a tree with a single populated branch, a shared tail and weakref.finalize. The probes dropped a chain 900 calls deep, in a generator's finally, in a finalizer and in a weakref callback, via dict.clear, key deletion and rebinding. A weak-callback closure owning a node, a finalizer that raised, and one that created another chain also gave identical output. [Release probes](r29-probes/codex/release) · [Callback ownership](r29-probes/codex/callback-ownership)
- **Python recursion.** Plain and mutual recursion, method calls, generator delegation, instance `__getattr__`, `__repr__`, `__eq__`, `__hash__`, `__iter__` and recursive formatting matched at limits 50, 200, the default 1000, and 3000. Catching and repeating gave the same counts. Sorted-key recursion matched through 1000; at 3000 neither side reached the configured limit. Decorator chains and recursion caught inside a finalizer or weak callback also matched at all four settings. Every printed `sys.getrecursionlimit()` matched. [Recursion rows](r29-probes/codex/recursion) · [Callback and decorator rows](r29-probes/codex/recursion-context)
- **Data walks.** At 200,000 list levels and 1024 KiB stack, all ten rows matched: shallow copy, sum with a list start, list and tuple conversion, len, bool, unpacking, reduce, identity equality and a hand-written iterative walk. The last counted exactly 200,000 levels. An auxiliary owner list allowed teardown one level at a time. At 100 levels and Python limit 50, both sides agreed on all tested list, tuple and dict comparison/search rows, exception repr/str, named-tuple repr/str, named-tuple and tuple-subclass hashing, deepcopy and pprint. The set/frozenset comparison, key, membership and hash rows agreed, including TypeError for an unhashable set. [Outer-layer and iterative operations](r29-probes/codex/shallow-operations) · [Bounded walks](r29-probes/codex/walk-supported) · [Sets](r29-probes/codex/frozen)
- **Slot controls.** All 72 rows agreed across 18 operations and four object shapes: names supplied by the instance dict, by instance `__getattr__`, by the metaclass, or set to None in the class. The operations exercised operator, itertools, functools, deque, struct, BytesIO, re, time, math, bisect, heapq, random, json, zlib, hashlib, binascii, len and list. [Programs and raw comparisons](r29-probes/codex/slots)
- **Shutdown warnings.** Neither side called the replacement for `_warnings.warn` in any of the 24 rows. The eight ignore-filter rows agreed byte for byte with the file in a global, class attribute, closure or cycle, with and without a replacement showwarning. Always/error stderr differences occurred in the already documented shutdown configuration. [Warning rows](r29-probes/codex/warning)
