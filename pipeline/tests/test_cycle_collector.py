"""The cycle collector compiled (step 3c, parts 1 to 3 of TODO's plan; the author's decisions of 2026-11-14): trial
deletion over candidate roots in runtime/include/bella/object.hpp, the runtime's kinds' traversals (runtime/src/core.cpp),
the gc module over it (runtime/src/gc.cpp, runtime/prelude/gc.py), and a scheduled collection at the look.

* `cycle_shapes.txt`: a cycle through every kind the runtime has, each let go of and then collected, as CPython 3.15.2
  finds them: instances, lists and dicts, a closure's cell, a bound method, a generator, a traceback and its frame's
  locals, super, a slice, a dict view, an iterator, sets and tuples, a partial, a property, weak references with and
  without a callback, a finaliser that revives its group, a group something outside holds, subclasses of dict and list,
  and gc.callbacks' phases and keys. What died is printed as a multiset (a group's order is open: D-04).
* The numbers are the runtime's own (D-04): what gc.collect() returns, get_count() and get_stats() are compared by their
  shapes alone; a collection runs automatically at the looks when the buffer passes the threshold, and not when the
  collector is disabled or the threshold is 0.

Run under pytest or directly: python3 -m pipeline.tests.test_cycle_collector
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from pipeline.tests.test_review_2026_11_19 import same

HERE = Path(__file__).resolve().parent

AUTOMATIC = '''
import gc
died = [0]
class N:
    def __del__(self):
        died[0] += 1
def make(count):
    for _ in range(count):
        n = N()
        n.me = n
    return died[0]
print("collected by the looks:", make(30000) > 25000)
gc.collect()
died[0] = 0
gc.disable()
print("disabled: none collected", make(30000) == 0, gc.isenabled())
gc.enable()
gc.collect()
died[0] = 0
gc.set_threshold(0)
print("threshold 0: none collected", make(30000) == 0, gc.get_threshold())
gc.set_threshold(2000)
print("collected again:", gc.collect() >= 29000, died[0] >= 29000)
'''

NUMBERS = '''
import gc
class K:
    pass
k = K()
k.me = k
del k
found = gc.collect()
print("collect:", type(found).__name__, found >= 1, gc.collect(0) >= 0, gc.collect(generation=1) >= 0)
count = gc.get_count()
print("get_count:", type(count).__name__, len(count), [type(c).__name__ for c in count])
stats = gc.get_stats()
print("get_stats:", type(stats).__name__, len(stats), [sorted(s) for s in stats], [type(v).__name__ for s in stats for v in s.values()])
'''

FINALIZED = '''
import gc
kept = []
class Back:
    def __del__(self):
        kept.append(self)
class Plain:
    pass
b = Back()
b.me = b
del b
gc.collect()
print("revived by its finaliser:", gc.is_finalized(kept[0]), len(kept))
p = Plain()
p.me = p
print("alive, no finaliser:", gc.is_finalized(p), "| not tracked:", gc.is_finalized(1), gc.is_finalized("s"))
gc.collect()
print("still alive:", gc.is_finalized(p))
'''

PROGRAMS = {"automatic": AUTOMATIC, "numbers": NUMBERS, "finalized": FINALIZED}


def pytest_generate_tests(metafunc: Any) -> None:
    if "program" in metafunc.fixturenames:
        metafunc.parametrize("program", sorted(PROGRAMS))


def test_programs(program: str) -> None:
    same(PROGRAMS[program])


def test_cycle_shapes() -> None:
    same((HERE / "cycle_shapes.txt").read_text(encoding="utf-8"))


if __name__ == "__main__":
    for name in sorted(PROGRAMS):
        same(PROGRAMS[name])
    test_cycle_shapes()
    print("ok")
