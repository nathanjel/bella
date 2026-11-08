# clause: C-7-45
# spec: section 7
# status: P1
# source: dialect specification section 7, Modules/_heapqmodule.c, Lib/heapq.py
"""The _heapq accelerator behind heapq: the ten functions' parsing (a list or a subclass, positional only, the clinic's messages),
the heaps they build and the items they return for the min and max variants over sizes on both sides of the cache-friendly
threshold, the comparisons made and their order (a class counting its __lt__ calls), the RuntimeError when a comparison changes
the list's size, and the heapq module's nlargest and nsmallest over them."""
# ruff: noqa: ANN001, ANN002, ANN003, ANN201, ANN202, ANN204, B018, B023, E501, E731, E741, E742, F601, PLR0133, SLF001
import _heapq
import heapq


def m(f):  # type: ignore[no-untyped-def]
    try:
        return repr(f())
    except Exception as e:
        return type(e).__name__ + ": " + str(e)


def gen(n):  # type: ignore[no-untyped-def]
    x = 7 + n
    while True:
        x = (x * 1103515245 + 12345) & 0x7FFFFFFF
        yield x


print("module:", [(n, type(getattr(_heapq, n)).__name__) for n in sorted(dir(_heapq)) if not n.startswith("__")], _heapq.__about__[:40], repr(_heapq.__doc__[:60]), heapq.heappush is _heapq.heappush, heapq.heapify_max is _heapq.heapify_max, heapq.__about__ == _heapq.__about__)
print("docs:", [repr(getattr(_heapq, n).__doc__) for n in ("heappush", "heappop", "heapify", "heapreplace", "heappushpop", "heappush_max", "heappop_max", "heapify_max", "heapreplace_max", "heappushpop_max")])
print("arguments:", m(lambda: _heapq.heappush((), 1)), m(lambda: _heapq.heappush([], 1, 2)), m(lambda: _heapq.heappush([])), m(lambda: _heapq.heappush(heap=[], item=1)), m(lambda: _heapq.heappop([])), m(lambda: _heapq.heappop(())), m(lambda: _heapq.heappop([], 1)), m(lambda: _heapq.heapreplace([], 1)), m(lambda: _heapq.heappushpop([], 1)), m(lambda: _heapq.heapify(())), m(lambda: _heapq.heapify([3, 1, 2])), m(lambda: _heapq.heappop_max([])), m(lambda: _heapq.heapreplace_max([], 1)), m(lambda: _heapq.heappushpop_max([], 5)), m(lambda: _heapq.heapify_max("ab")), m(lambda: _heapq.heappush([1], "a")), m(lambda: _heapq.heappushpop([1], "a")), m(lambda: _heapq.heapify([1, "a"])), m(lambda: _heapq.heapify_max(heap=[])), m(lambda: _heapq.heappop_max()), m(lambda: _heapq.heappush_max([], 1, 2)))  # type: ignore[arg-type,call-arg,misc,no-untyped-call,type-var]


h = [3, 1, 2]
print("small:", _heapq.heapify(h), h, _heapq.heappush(h, 0), h, _heapq.heappop(h), h, _heapq.heappushpop(h, -1), _heapq.heappushpop(h, 5), h, _heapq.heapreplace(h, 4), h)  # type: ignore[func-returns-value]
g = gen(1)  # type: ignore[no-untyped-call]
for n in (0, 1, 2, 3, 4, 5, 7, 8, 9, 15, 16, 17, 100, 1000, 2500, 2501, 2502, 3000, 4097, 6000):
    base = [next(g) % 1009 for _ in range(n)]
    mn, mx = list(base), list(base)
    _heapq.heapify(mn)
    _heapq.heapify_max(mx)
    okmin = all(mn[i] <= mn[2 * i + 1] and (2 * i + 2 >= n or mn[i] <= mn[2 * i + 2]) for i in range(n // 2))
    okmax = all(mx[i] >= mx[2 * i + 1] and (2 * i + 2 >= n or mx[i] >= mx[2 * i + 2]) for i in range(n // 2))
    popped = [_heapq.heappop(list(mn)) if n else None, _heapq.heappop_max(list(mx)) if n else None]
    print("heapify", n, mn[:6], mx[:6], okmin, okmax, popped, sum(mn[:50]), sum(mx[-50:]))
mn = []
mx = []
log = []
g = gen(2)  # type: ignore[no-untyped-call]
for _ in range(300):
    v = next(g) % 500
    _heapq.heappush(mn, v)
    _heapq.heappush_max(mx, v)
    if len(mn) > 40:
        log.append((_heapq.heappop(mn), _heapq.heappop_max(mx), _heapq.heapreplace(mn, v // 2), _heapq.heapreplace_max(mx, v * 2 % 500), _heapq.heappushpop(mn, v + 1), _heapq.heappushpop_max(mx, v - 1)))
print("operations:", len(mn), len(mx), mn[:8], mx[:8], log[:6], log[-3:], sum(a for a, _, _, _, _, _ in log), sum(b for _, b, _, _, _, _ in log))
drained = []
while mn:
    drained.append(_heapq.heappop(mn))
drained_max = []
while mx:
    drained_max.append(_heapq.heappop_max(mx))
print("drained:", drained == sorted(drained), drained_max == sorted(drained_max, reverse=True), drained[:5], drained_max[:5], len(drained), len(drained_max))


class K:
    calls: list[tuple[int, int]] = []

    def __init__(self, v):  # type: ignore[no-untyped-def]
        self.v = v

    def __lt__(self, o):  # type: ignore[no-untyped-def]
        K.calls.append((self.v, o.v))
        return self.v < o.v

    def __repr__(self):  # type: ignore[no-untyped-def]
        return "K" + str(self.v)


ks = [K(5), K(3), K(8), K(1), K(9), K(2), K(7)]  # type: ignore[no-untyped-call]
_heapq.heapify(ks)
print("comparisons:", ks, K.calls)
K.calls = []
_heapq.heappush(ks, K(0))  # type: ignore[no-untyped-call]
print(" push:", ks, K.calls)
K.calls = []
print(" pop:", _heapq.heappop(ks), ks, K.calls)
K.calls = []
print(" pushpop:", _heapq.heappushpop(ks, K(4)), _heapq.heappushpop(ks, K(-1)), ks, K.calls)  # type: ignore[no-untyped-call]
K.calls = []
print(" replace:", _heapq.heapreplace(ks, K(6)), ks, K.calls)  # type: ignore[no-untyped-call]
K.calls = []
kmax = [K(5), K(3), K(8), K(1), K(9), K(2), K(7)]  # type: ignore[no-untyped-call]
_heapq.heapify_max(kmax)
print(" max:", kmax, K.calls)
K.calls = []
print(" max ops:", _heapq.heappop_max(kmax), _heapq.heappushpop_max(kmax, K(10)), _heapq.heappushpop_max(kmax, K(0)), _heapq.heapreplace_max(kmax, K(4)), kmax, K.calls)  # type: ignore[no-untyped-call]


class Shrinks:
    def __init__(self, heap, v):  # type: ignore[no-untyped-def]
        self.heap = heap
        self.v = v

    def __lt__(self, o):  # type: ignore[no-untyped-def]
        if self.heap:
            self.heap.pop()
        return self.v < o.v


bad = []  # type: ignore[var-annotated]
bad.extend(Shrinks(bad, v) for v in (5, 4, 3, 2, 1))  # type: ignore[no-untyped-call]
print("size change:", m(lambda: _heapq.heapify(bad)), len(bad), m(lambda: _heapq.heappush(bad, Shrinks(bad, 0))), len(bad), m(lambda: _heapq.heapify([])), m(lambda: _heapq.heappush([Shrinks([], 1)], Shrinks([], 0))))  # type: ignore[no-untyped-call]
print("package:", heapq.nlargest(3, [5, 1, 9, 3, 7, 9]), heapq.nsmallest(3, [5, 1, 9, 3, 7, 9]), heapq.nlargest(2, ["aa", "b", "ccc"], key=len), heapq.nsmallest(0, [1, 2]), heapq.nlargest(5, [1, 2]), heapq.nsmallest(2, iter(range(100, 0, -1))), m(lambda: heapq.nlargest(1, [1, "a"])))  # type: ignore[no-untyped-call,type-var]
