# clause: C-7-42
# spec: section 7
# status: P1
# source: dialect specification section 7, Modules/_bisectmodule.c, Lib/bisect.py
"""The _bisect module behind bisect: the four functions' argument parsing (lo a non-negative index, hi an index or None where -1 means
the length, key keyword-only, the clinic's messages), PySequence_Size and the sequence slot's errors for what is no sequence, the
comparisons made (x < key(a[mid]) for the right side, key(a[mid]) < x for the left, so a reflected comparison and a NotImplemented
behave as the operator's), insort's single key call and its insert through the object, and the bisect module's names."""
# ruff: noqa: ANN001, ANN002, ANN003, ANN201, ANN202, ANN204, B018, B023, E501, E731, E741, E742, F601, PLR0133, SLF001
import _bisect
import bisect
import collections
import types


def m(f):  # type: ignore[no-untyped-def]
    try:
        return repr(f())
    except Exception as e:
        return type(e).__name__ + ": " + str(e)


print("module:", repr(_bisect.__doc__), [n for n in dir(_bisect) if not n.startswith("__")], bisect.bisect is _bisect.bisect_right, bisect.insort is _bisect.insort_right, bisect.bisect_left is _bisect.bisect_left, bisect.insort_left is _bisect.insort_left, sorted(n for n in dir(bisect) if not n.startswith("_")))
print("docs:", repr(_bisect.bisect_right.__doc__), repr(_bisect.bisect_left.__doc__), repr(_bisect.insort_right.__doc__), repr(_bisect.insort_left.__doc__), type(_bisect.bisect_right).__name__, _bisect.bisect_right.__name__, _bisect.insort_left.__qualname__, _bisect.bisect_left.__module__)
a = [1, 2, 2, 3]
print("bounds:", m(lambda: _bisect.bisect_right(a, 2)), m(lambda: _bisect.bisect_left(a, 2)), m(lambda: _bisect.bisect_right(a, 2, 0, -1)), m(lambda: _bisect.bisect_right(a, 2, hi=-1)), m(lambda: _bisect.bisect_right(a, 2, hi=-2)), m(lambda: _bisect.bisect_right(a, 2, lo=-1)), m(lambda: _bisect.bisect_right(a, 2, lo=1.5)), m(lambda: _bisect.bisect_right(a, 2, hi=1.5)), m(lambda: _bisect.bisect_right(a, 2, hi="x")), m(lambda: _bisect.bisect_right(a, 2, lo=2**70)), m(lambda: _bisect.bisect_right(a, 2, hi=2**70)), m(lambda: _bisect.bisect_right(a, 2, hi=-2**70)), m(lambda: _bisect.bisect_right(a, 2, lo=-2**70)), m(lambda: _bisect.bisect_right(a, 2, lo=10)), m(lambda: _bisect.bisect_right(a, 2, lo=True)), m(lambda: _bisect.bisect_right(a, 2, hi=None)), m(lambda: _bisect.bisect_right(a, 2, 1, None)), m(lambda: _bisect.bisect_right(a, 2, lo=None)), m(lambda: _bisect.bisect_right([], 1)), m(lambda: _bisect.bisect_right([], 1, 5)), m(lambda: _bisect.bisect_right([1], 1, 3, 2)), m(lambda: _bisect.bisect_right(a, 2, 1, 100)), m(lambda: _bisect.bisect_left(a, 0)), m(lambda: _bisect.bisect_left(a, 4)), m(lambda: _bisect.bisect_right(a, 0)), m(lambda: _bisect.bisect_right(a, 4)), m(lambda: _bisect.bisect_left(a, 2, 2)), m(lambda: _bisect.bisect_left(a, 2, 0, 1)))  # type: ignore[call-overload,no-untyped-call]


class I:
    def __index__(self):  # type: ignore[no-untyped-def]
        return 1


class Big:
    def __index__(self):  # type: ignore[no-untyped-def]
        return 2**70


print("indexes:", m(lambda: _bisect.bisect_right([1, 2, 3], 2, I(), I())), m(lambda: _bisect.bisect_right([1, 2, 3], 2, hi=Big())), m(lambda: _bisect.bisect_right([1, 2, 3], 2, lo=Big())), m(lambda: _bisect.bisect_right([1, 2, 3], 2, lo=I(), hi=3)))  # type: ignore[call-overload,no-untyped-call]
print("arguments:", m(lambda: _bisect.bisect_right()), m(lambda: _bisect.bisect_right(a)), m(lambda: _bisect.bisect_right(a, 1, 0, 1, None)), m(lambda: _bisect.bisect_right(a, 1, 0, 1, key=None)), m(lambda: _bisect.bisect_right(a, 1, bogus=1)), m(lambda: _bisect.bisect_right(a=a, x=1)), m(lambda: _bisect.bisect_right(a, 1, x=2)), m(lambda: _bisect.insort_right(a, 1, 0, 1, None)), m(lambda: _bisect.insort_left()), m(lambda: _bisect.bisect_right(a, 1, key=str)), m(lambda: _bisect.bisect_right([3, 2, 1], 2, key=lambda v: -v)), m(lambda: _bisect.bisect_right(a, 1, kye=str)), m(lambda: _bisect.bisect_right(a, 1, 0, 1, key=None, bogus=1)), m(lambda: _bisect.bisect_right(a, 1, 0, 1, 2, key=None)), m(lambda: _bisect.bisect_right(x=1)), m(lambda: _bisect.bisect_right(a, bogus=1)), m(lambda: _bisect.bisect_right(a, 1, a=2)), m(lambda: _bisect.bisect_right(a, 1, lo=0, a=2)), m(lambda: _bisect.bisect_left(a, 1, lo=1, hi=3, key=None)), m(lambda: _bisect.insort_left(list(a), 1, lo=1, hi=3, key=None)))  # type: ignore[arg-type,call-overload,no-untyped-call]


class L:
    def __len__(self):  # type: ignore[no-untyped-def]
        return 3


class G:
    def __init__(self):  # type: ignore[no-untyped-def]
        self.calls = []

    def __len__(self):  # type: ignore[no-untyped-def]
        return 5

    def __getitem__(self, i):  # type: ignore[no-untyped-def]
        self.calls.append(i)
        return i * 10


class D(dict):  # type: ignore[type-arg]
    pass


class D2(dict):  # type: ignore[type-arg]
    def __len__(self):  # type: ignore[no-untyped-def]
        return 4

    def __getitem__(self, i):  # type: ignore[no-untyped-def]
        return i


g = G()  # type: ignore[no-untyped-call]
print("sequences:", m(lambda: _bisect.bisect_right({1: 2}, 1)), m(lambda: _bisect.bisect_right({1: 2}, 1, hi=1)), m(lambda: _bisect.bisect_right(5, 1)), m(lambda: _bisect.bisect_right(5, 1, hi=1)), m(lambda: _bisect.bisect_right("abc", "b")), m(lambda: _bisect.bisect_right((1, 2), 2)), m(lambda: _bisect.bisect_right(range(10), 4)), m(lambda: _bisect.bisect_right(b"abc", 98)), m(lambda: _bisect.bisect_right(None, 1)), m(lambda: _bisect.bisect_right(a, "x")), m(lambda: _bisect.bisect_right(L(), 1)), m(lambda: _bisect.bisect_right(L(), 1, hi=2)), m(lambda: _bisect.bisect_right(g, 25)), g.calls, m(lambda: _bisect.bisect_right(g, 25, hi=3)), g.calls, m(lambda: _bisect.bisect_right(D(), 1)), m(lambda: _bisect.bisect_right(D(), 1, hi=2)), m(lambda: _bisect.bisect_right(D2(), 2)), m(lambda: _bisect.insort_right(D2(), 2)), m(lambda: _bisect.insort_right((1, 2), 3)), m(lambda: _bisect.insort_right("ab", "c")), m(lambda: _bisect.bisect_right(set(), 1)), m(lambda: _bisect.bisect_right(set(), 1, hi=1)), m(lambda: _bisect.bisect_right(frozenset(), 1)))  # type: ignore[call-overload,no-untyped-call]
print("c mappings:", m(lambda: _bisect.bisect_right(types.MappingProxyType({}), 1)), m(lambda: _bisect.bisect_right(types.MappingProxyType({}), 1, hi=1)), m(lambda: _bisect.bisect_right(collections.deque([1, 2, 3]), 2)), m(lambda: _bisect.bisect_right(collections.defaultdict(int), 1)), m(lambda: _bisect.bisect_right(collections.defaultdict(int), 1, hi=1)), m(lambda: _bisect.bisect_right(list[int], 1)), m(lambda: _bisect.bisect_right(list[int], 1, hi=1)), m(lambda: _bisect.bisect_right(int | str, 1)), m(lambda: _bisect.bisect_right(int | str, 1, hi=1)))  # type: ignore[arg-type,call-overload,no-untyped-call,type-var]


class Ins:
    def __init__(self):  # type: ignore[no-untyped-def]
        self.log = []

    def __len__(self):  # type: ignore[no-untyped-def]
        return 2

    def __getitem__(self, i):  # type: ignore[no-untyped-def]
        return [1, 3][i]

    def insert(self, i, v):  # type: ignore[no-untyped-def]
        self.log.append((i, v))


ins = Ins()  # type: ignore[no-untyped-call]
print("insort:", m(lambda: _bisect.insort_right(ins, 2)), ins.log, m(lambda: _bisect.insort_left(ins, 1, key=lambda v: v)), ins.log, m(lambda: _bisect.insort_right(L(), 1)))  # type: ignore[call-overload,no-untyped-call]
b = [1, 2, 2, 3]
_bisect.insort_right(b, 2)
_bisect.insort_left(b, 0)
_bisect.insort_right(b, 9)
_bisect.insort_left(b, 2, 0, 2)
print("insort lists:", b, m(lambda: _bisect.insort_right(b, 5, lo=-1)), m(lambda: _bisect.insort_right(b, 5, hi=2.5)), b)  # type: ignore[call-overload,no-untyped-call]


class K:
    def __init__(self, v):  # type: ignore[no-untyped-def]
        self.v = v

    def __lt__(self, o):  # type: ignore[no-untyped-def]
        print("  lt", self.v, o.v)
        return self.v < o.v


ks = [K(1), K(3)]  # type: ignore[no-untyped-call]
print("comparisons:")
print(" ", m(lambda: _bisect.bisect_right(ks, K(2))), m(lambda: _bisect.bisect_left(ks, K(2))), m(lambda: _bisect.insort_left(ks, K(2))), [k.v for k in ks])  # type: ignore[no-untyped-call]


class Odd:
    def __lt__(self, o):  # type: ignore[no-untyped-def]
        return NotImplemented


class Gt:
    def __gt__(self, o):  # type: ignore[no-untyped-def]
        print("  gt", o)
        return True


print("not implemented:", m(lambda: _bisect.bisect_right([Odd()], Odd())), m(lambda: _bisect.bisect_right([1], Odd())), m(lambda: _bisect.bisect_right([Odd()], 1)), m(lambda: _bisect.bisect_right([Gt()], 5)), m(lambda: _bisect.bisect_left([Gt()], 5)), m(lambda: _bisect.bisect_right([5], Gt())))  # type: ignore[no-untyped-call]
cnt = []
print("key calls:", m(lambda: _bisect.insort_right([1, 2], 5, key=lambda v: (cnt.append(v), v)[1])), cnt, m(lambda: _bisect.bisect_right([1, 2], 5, key=lambda v: (cnt.append(v), v)[1])), cnt)  # type: ignore[func-returns-value,no-untyped-call]
rows = [("b", 2), ("a", 1), ("c", 3)]
print("keyed:", m(lambda: _bisect.bisect_right(rows, 2, key=lambda r: r[1])), m(lambda: _bisect.insort_right(rows, ("d", 2), key=lambda r: r[1])), rows, m(lambda: _bisect.bisect_left(rows, ("a", 1))), m(lambda: _bisect.bisect_right(rows, ("a", 1))))  # type: ignore[no-untyped-call]
grades = [60, 70, 80, 90]
print("package:", [bisect.bisect(grades, score) for score in (33, 99, 77, 70, 89, 90)], [bisect.bisect_left(grades, score) for score in (33, 99, 77, 70, 89, 90)], m(lambda: bisect.insort(grades, 75)), grades, m(lambda: bisect.bisect(grades, 1, lo=-1)))  # type: ignore[no-untyped-call]
