# clause: C-7-20
# spec: section 7
# status: P1
# source: dialect specification section 7 (itertools is in the phase-1 closure), Modules/itertoolsmodule.c
"""itertools by itself: every type on plain input, what each does at the end of its input and after
an exception, the groups of groupby, tee's copies past one block of its chain, the repr of count and
repeat, and when an item a finaliser can see dies, which is what the recycled result tuples decide."""
# ruff: noqa: B018, B905, B911, C408, C416, E721, RUF015, PLR0124, UP037
import itertools as it


def failed(f: object) -> str:
    try:
        f()  # type: ignore[operator]
    except Exception as exc:
        return type(exc).__name__
    return "no error"


# ---- plain use
print(list(it.chain("ab", (), [1])), list(it.chain.from_iterable(["ab", (1,)])), list(it.islice("abcde", 2)), list(it.islice("abcde", 1, 3)), list(it.islice("abcde", 0, None, 2)), list(it.islice("abcde", None)))
print(list(it.product("ab", repeat=2)), list(it.product("ab", "x")), list(it.product()), list(it.product("", "a")), list(it.combinations("abc", 2)), list(it.combinations("a", 2)), list(it.combinations_with_replacement("ab", 2)), list(it.permutations("abc", 2)), list(it.permutations("ab")))
print(list(it.accumulate([1, 2, 3])), list(it.accumulate([1, 2], max, initial=5)), list(it.batched("abcde", 2)), list(it.pairwise("abc")), list(it.compress("abc", [1, 0, 1])), list(it.takewhile(bool, [1, 0, 1])), list(it.dropwhile(bool, [1, 0, 1])), list(it.filterfalse(None, [0, 1])), list(it.starmap(pow, [(2, 3)])), list(it.zip_longest("ab", "c", fillvalue="-")))
print([(k, list(g)) for k, g in it.groupby("aabbca")], [(k, list(g)) for k, g in it.groupby([1, 2, 3], lambda x: x // 2)], list(it.islice(it.cycle("ab"), 5)), list(it.islice(it.count(5, 2), 2)), list(it.repeat("a", 2)), [list(t) for t in it.tee("ab", 2)], it.tee("a", 0))

# ---- what they say of themselves
print(it.chain, type(it.chain()).__name__, it.chain.__module__, it.chain.__qualname__, it.chain.__mro__, it.tee, type(it.tee).__name__, it.count(3), it.count(3, 2), it.count(2**64), it.repeat("a"), it.repeat("a", 2), it.repeat("a", -5), it.repeat("a", 2).__length_hint__(), it.chain[int])
print(failed(lambda: it.chain(1)), failed(lambda: list(it.chain(1))), failed(lambda: it.chain(x=1)), failed(lambda: it.islice("a", -1)), failed(lambda: it.islice("a", 0, 1, 0)), failed(lambda: it.batched("a", 0)), failed(lambda: it.combinations("a", -1)), failed(lambda: it.permutations("a", "b")), failed(lambda: it.count("a")), failed(lambda: it.repeat(1, "a")), failed(lambda: it.tee("a", -1)), failed(lambda: it.product(repeat=-1)), failed(lambda: it.repeat("a").__length_hint__()), failed(lambda: list(it.batched("abc", 2, strict=True))))  # type: ignore[arg-type,call-arg,call-overload]
print(failed(lambda: setattr(it.chain, "x", 1)), failed(lambda: setattr(it.chain(), "x", 1)), failed(lambda: type("S", (it.chain,), {})), failed(lambda: type("S", (it._tee,), {})), failed(lambda: type("S", (it._grouper,), {})), failed(lambda: type("S", (it.chain, it.count), {})), iter(it.count()).__class__.__name__)  # type: ignore[attr-defined]


# ---- the end, and after an exception
class Raises:
    def __init__(self, items: list[int]) -> None:
        self.items = items
        self.first = True

    def __iter__(self) -> "Raises":
        return self

    def __next__(self) -> int:
        if self.items:
            return self.items.pop(0)
        if self.first:
            self.first = False
            raise ValueError
        raise StopIteration


def after(i: object, n: int = 4) -> list[object]:
    out: list[object] = []
    for _ in range(n):
        try:
            out.append(next(i))  # type: ignore[call-overload]
        except StopIteration:
            out.append("stop")
        except ValueError:
            out.append("error")
    return out


print(after(it.chain(Raises([1]), "z")), after(it.islice(Raises([1]), 3)), after(it.accumulate(Raises([1]))), after(it.batched(Raises([1]), 3)), after(it.pairwise(Raises([1]))), after(it.compress(Raises([1]), [1, 1])), after(it.takewhile(bool, Raises([1]))), after(it.zip_longest(Raises([1]), "abc")), after(it.cycle(Raises([1]))), after(it.tee(Raises([1]))[0]))


# ---- groups
gb = it.groupby("aabbc")
k1, g1 = next(gb)
print(k1, next(g1))
k2, g2 = next(gb)
print(k2, list(g1), next(g2), list(g2), list(g1))

# ---- tee past its first block
a, b = it.tee(range(200))
print(next(a), sum(a), next(b), list(b)[-1], next(a, "end"))
c = a.__copy__()  # type: ignore[attr-defined]
print(next(c, "end"), type(c).__name__, it.tee(a)[0].__class__.__name__)

# ---- when an item dies
log: list[str] = []


class D:
    def __init__(self, n: int) -> None:
        self.n = n

    def __del__(self) -> None:
        log.append("del " + str(self.n))

    def __repr__(self) -> str:
        return "D" + str(self.n)


def source(n: int = 4) -> map[D]:
    return map(D, range(n))


for make in (lambda: it.pairwise(source()), lambda: it.islice(source(), 1, 4, 2), lambda: it.zip_longest(source(1), source(2)), lambda: it.batched(source(), 2), lambda: it.accumulate(source(2), lambda x, y: y), lambda: it.takewhile(lambda x: x.n < 1, source())):
    i = make()
    for _ in range(3):
        r = next(i, "end")
        print(r, log)
        log.clear()
        del r
        print(log)
        log.clear()
    del i
    print(log)
    log.clear()

p = it.pairwise(source(5))
first = next(p)
second = next(p)
print(first is second, first, second)
del second
third = next(p)
print(third, log)
log.clear()
del first, third, p
print(log)
log.clear()
for make2 in (lambda: it.pairwise(range(5)), lambda: it.product("ab", "cd"), lambda: it.combinations("abcd", 2), lambda: it.zip_longest("abcde", "de")):
    j = make2()
    x = id(next(j))
    y = id(next(j))
    kept = next(j)
    z = next(j)
    print(x == y, kept is z, kept, z)
