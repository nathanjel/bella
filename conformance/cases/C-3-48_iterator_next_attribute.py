# clause: C-3-48
# spec: section 3
# status: P1
# source: dialect specification section 3, Objects/iterobject.c, listobject.c, tupleobject.c, rangeobject.c, unicodeobject.c,
#         bytesobject.c, dictobject.c, setobject.c (tp_iter = PyObject_SelfIter, tp_iternext), Lib/heapq.py (merge)
"""The built-in iterators' `__next__` and `__iter__` as attributes: a bound method-wrapper for each iterator type, which answers
the next item, raises StopIteration with no arguments at the end, and takes no arguments; the unbound slot wrappers on the types;
and heapq.merge, which binds `__next__` once per input."""
# ruff: noqa: ANN001, ANN002, ANN003, ANN201, ANN202, ANN204, B018, B023, E501, E731, E741, E742, F601, PLR0133, SLF001
import heapq
its = [iter([1, 2, 3]), iter((4,)), iter(range(2)), iter("ab"), iter(b"xy"), iter({1: 2}), iter({1: 2}.values()), iter({1: 2}.items()), reversed([1, 2]), reversed({3: 4}), iter({5, 6}), iter(bytearray(b"q")), iter(reversed((7, 8)))]
for it in its:
    n = it.__next__
    i = it.__iter__
    print(type(it).__name__, type(n).__name__, n.__name__, repr(n)[:12], i() is it, n(), list(it), end=" | ")
    try:
        n()
    except StopIteration as e:
        print("stop", e.args)
    try:
        n(1)  # type: ignore[call-arg]
    except TypeError as e:
        print("  ", e)
print(list(heapq.merge([1, 4, 7], [2, 5, 8], [3, 6, 9])), list(heapq.merge([9, 5, 1], [8, 4], reverse=True)), list(heapq.merge(["ab", "c"], ["b", "dd"], key=len)), list(heapq.merge()), list(heapq.merge([], [1])))
print(type(iter([]).__next__).__name__, type(type(iter([])).__next__).__name__, type(iter([])).__next__.__name__, type(iter([])).__iter__(iter([1])) is not None, type(iter([])).__next__(iter([5])), type(iter(())).__next__.__qualname__)  # type: ignore[arg-type]
try:
    type(iter([])).__next__(iter(()))
except TypeError as e:
    print(e)
