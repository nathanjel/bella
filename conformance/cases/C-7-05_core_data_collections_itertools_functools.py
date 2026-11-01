# clause: C-7-05
# spec: section 7
# status: P1
# source: dialect specification section 7, Core data (collections, itertools, functools, operator, heapq, bisect)
"""Core data modules, part 1: the results phase 1 must reproduce exactly."""
import bisect
import collections
import functools
import heapq
import itertools
import operator

words = "the quick brown fox jumps over the lazy dog the end".split()
c = collections.Counter(words)
print(c.most_common(3), c["the"], c["missing"], sorted((c + collections.Counter(fox=2)).items())[:3])
d = collections.deque(range(5), maxlen=4)
d.rotate(1)
d.appendleft(9)
print(list(d), d.maxlen)
od = collections.OrderedDict.fromkeys("abc", 0)
od.move_to_end("a")
print(list(od), od.popitem(last=False))
dd: collections.defaultdict[str, list[int]] = collections.defaultdict(list)
for i, w in enumerate(words[:4]):
    dd[w[0]].append(i)
print(dict(dd), collections.ChainMap({"a": 1}, {"a": 2, "b": 3})["a"], list(collections.ChainMap({"a": 1}, {"b": 3})))
Point = collections.namedtuple("Point", "x y", defaults=[0])
p = Point(1)
print(p, p._replace(y=5), p._asdict(), Point._fields)

print([(k, len(list(g))) for k, g in itertools.groupby(sorted(words, key=len), key=len)])
print(list(itertools.accumulate([1, 2, 3, 4], operator.mul)), list(itertools.pairwise("abcd")))
print(list(itertools.product("ab", repeat=2)), list(itertools.permutations(range(3), 2))[:4])
print(list(itertools.islice(itertools.count(10, 3), 4)), list(itertools.batched(range(7), 3, strict=False)))
print(list(itertools.chain.from_iterable([[1], [2, 3]])), list(itertools.zip_longest("ab", "xyz", fillvalue="-")))
print(list(itertools.combinations_with_replacement("ab", 2)), list(itertools.compress("abcd", [1, 0, 1, 1])))

print(functools.reduce(operator.add, range(10), 100), functools.partial(int, base=2)("1011"))


@functools.lru_cache(maxsize=2)
def square(n: int) -> int:
    return n * n


print([square(n) for n in (1, 2, 1, 3, 1)], square.cache_info())


@functools.total_ordering
class Version:
    def __init__(self, n: int) -> None:
        self.n = n

    def __eq__(self, other: object) -> bool:
        return isinstance(other, Version) and self.n == other.n

    def __lt__(self, other: "Version") -> bool:  # noqa: UP037  # total_ordering reads this annotation
        return self.n < other.n

    __hash__ = None  # type: ignore[assignment]  # defining __eq__ removes hashing; said explicitly


print(Version(1) <= Version(2), Version(3) >= Version(2), Version(2) > Version(2))
rows = [{"n": 3, "s": "c"}, {"n": 1, "s": "a"}, {"n": 2, "s": "b"}]
print(sorted(rows, key=operator.itemgetter("n"))[0], operator.methodcaller("upper")("x"), operator.attrgetter("real")(3))
h = [5, 1, 8, 3, 9, 2]
heapq.heapify(h)
print(h, heapq.heappop(h), heapq.nsmallest(2, [7, 3, 5]), heapq.nlargest(2, [7, 3, 5]), list(heapq.merge([1, 4], [2, 3])))
sl = [1, 3, 3, 5]
print(bisect.bisect_left(sl, 3), bisect.bisect_right(sl, 3), bisect.bisect(sl, 4))
bisect.insort(sl, 4)
print(sl)
