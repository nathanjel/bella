# clause: C-7-25
# spec: section 7
# status: P1
# source: dialect specification section 7, Modules/_functoolsmodule.c, Lib/functools.py
"""functools over _functools: partial with its placeholders, keywords and merging; cmp_to_key; reduce; the three kinds of
lru_cache, what each evicts and when a key's hash runs; and what the module builds from them."""
# ruff: noqa: ANN001, ANN002, ANN003, ANN201, ANN202, ANN204, B006, B018, B019, B023, B024, B027, C408, E731, PLR0133, RUF015, SIM118, UP033, UP037
import functools
import _functools  # type: ignore[import-not-found]


def failed(f: object) -> str:
    try:
        f()  # type: ignore[operator]
    except Exception as exc:
        return type(exc).__name__
    return "no error"


def add(*a, **k):  # type: ignore[no-untyped-def]
    return a, k


P = functools.partial  # type: ignore[misc,operator]
X = functools.Placeholder
print(P is _functools.partial, P.__name__, P.__module__, P.__qualname__, type(X).__name__, type(X).__module__, repr(X), X is type(X)(), X.__reduce__(), functools.reduce is _functools.reduce, functools.cmp_to_key is _functools.cmp_to_key, functools._lru_cache_wrapper is _functools._lru_cache_wrapper)

# ---- partial
print(P(add)(), P(add, 1)(), P(add, 1)(2), P(add, a=1)(), P(add, a=1)(b=2), P(add, a=1)(a=2), P(add, 1, a=1)(2, b=2), P(P(add, 1), 2)(3), P(P(add, a=1), b=2)(), P(P(add, a=1), a=2)(), P(add, X, 1)(0), P(add, X, 1, X, 2)(0, 1), P(add, X, 1)(0, 9), P(P(add, X, 1), 0)(), P(P(add, X, 1), 0, 2)(), P(P(add, X, X, 1), X, 0)(9), P(P(add, X, 1), X, 2)(0), P(add, X, 1, k=1)(0, j=2))
p = P(add, 1, 2, a=3)
print(p.func is add, p.args, p.keywords, type(p).__name__, repr(p).endswith("(1, 2)" ) or 0, repr(P(max, 1, a=2)), repr(P(max, X, 2)), str(P(max)), P(P(max, 1), 2).func is max, P(P(max, 1), 2).args, callable(p), hash(p) == hash(p), p == p, p != P(add), p.__dict__, vars(p), hasattr(p, "__weakref__"), hasattr(p, "x"))
p.x = 1  # type: ignore[attr-defined]
print(p.x, p.__dict__, P(p, 9).func is p, P(p, 9).args, P(p).args)  # type: ignore[attr-defined]
del p.x  # type: ignore[attr-defined]
print(p.__dict__, P(p).func is p)
q = P(add)
q.__dict__
print(P(q).func is q)
r = P(add, 1, a=2)
print(r.__reduce__()[0] is P, r.__reduce__()[1][0] is add, r.__reduce__()[2][1:], r.__setstate__((max, (1,), {"default": 2}, {"n": 1})), r.func is max, r.args, r.keywords, r.n, r.__reduce__()[2][1:], failed(lambda: r.__setstate__(1)), failed(lambda: r.__setstate__((1, 2))), failed(lambda: r.__setstate__((1, (), None, None))), failed(lambda: r.__setstate__((max, 1, None, None))), failed(lambda: r.__setstate__((max, (), 1, None))), failed(lambda: r.__setstate__((max, (), None, 1))), failed(lambda: r.__setstate__((max, (X,), None, None))), r.__setstate__((max, (X, 1), None, None)), r(0), r.keywords)  # type: ignore[attr-defined]
print(failed(lambda: P()), failed(lambda: P(1)), failed(lambda: P(None)), failed(lambda: P(add, X)), failed(lambda: P(add, 1, X)), failed(lambda: P(add, a=X)), failed(lambda: P(add, X, 1)()), failed(lambda: P(add, X, X, 1)(0)), failed(lambda: setattr(p, "func", 1)), failed(lambda: setattr(p, "args", 1)), failed(lambda: setattr(p, "keywords", 1)), failed(lambda: delattr(p, "func")), failed(lambda: delattr(p, "nothing")), failed(lambda: p.nothing), failed(lambda: type(X)(1)), failed(lambda: type(X)(a=1)), failed(lambda: type("Z", (type(X),), {})))  # type: ignore[arg-type,attr-defined,call-arg]


class Sub(P):  # type: ignore[type-arg]
    pass


class M:
    pm = P(add, "bound")
    cached = functools.partial(lambda self: "x")


print(Sub(add, 1)(2), type(Sub(add, 1)).__name__, repr(Sub(max, 1)), Sub(Sub(add, 1), 2).args, Sub(P(add, 1), 2).args, P(Sub(add, 1), 2).args, type(P(Sub(add, 1), 2)).__name__, type(Sub(P(add, 1), 2)).__name__, M().pm(1)[0][0].__class__.__name__, M.pm(1), M().pm.__self__.__class__.__name__, M().pm.__func__ is M.pm, M.__dict__["pm"].__get__(None, M) is M.pm, failed(lambda: M.__dict__["pm"].__get__(None, None)), failed(lambda: M.__dict__["pm"].__get__()), P[int].__origin__ is P, P.__class_getitem__(int).__args__, repr(type(X)), repr(P))  # type: ignore[attr-defined]

# ---- reduce
print(functools.reduce(lambda a, b: a + b, [1, 2, 3]), functools.reduce(lambda a, b: a + b, [1, 2, 3], 10), functools.reduce(lambda a, b: a + b, [], 10), functools.reduce(lambda a, b: a + b, [5]), functools.reduce(lambda a, b: a + b, [1, 2], initial=10), functools.reduce(lambda a, b: a + b, (i for i in [1, 2])), functools.reduce(lambda a, b: a * b, range(1, 5)), functools.reduce(max, [1, 3, 2], 0), failed(lambda: functools.reduce()), failed(lambda: functools.reduce(max)), failed(lambda: functools.reduce(max, 1)), failed(lambda: functools.reduce(max, [])), failed(lambda: functools.reduce(1, [1, 2])), failed(lambda: functools.reduce(max, [1], 2, 3)), failed(lambda: functools.reduce(max, [1], 2, initial=3)), failed(lambda: functools.reduce(max, [1], x=3)), failed(lambda: functools.reduce(function=max, iterable=[1])))  # type: ignore[call-overload]

# ---- cmp_to_key
K = functools.cmp_to_key(lambda a, b: b - a)  # type: ignore[operator]
print(sorted([1, 3, 2], key=K), max([1, 3], key=K), min([1, 3], key=K), type(K).__name__, type(K).__module__, K(1).obj, K(obj=2).obj, K.obj, K(1) < K(2), K(1) > K(2), K(1) <= K(1), K(1) >= K(1), K(1) == K(1), K(1) != K(1), K(1) == K(2), failed(lambda: K(1) < 1), failed(lambda: 1 < K(1)), failed(lambda: K(1) == 1), failed(lambda: K < K(1)), failed(lambda: K(1) < K), failed(lambda: hash(K(1))), failed(lambda: {K(1)}), failed(lambda: K()), failed(lambda: K(1, 2)), failed(lambda: K(x=1)), failed(lambda: functools.cmp_to_key()), failed(lambda: functools.cmp_to_key(1, 2)), failed(lambda: type(K)()), functools.cmp_to_key(mycmp=lambda a, b: 0)(1).obj, failed(lambda: functools.cmp_to_key(1)(1) < functools.cmp_to_key(1)(2)), functools.cmp_to_key(lambda a, b: 1.5)(1) > functools.cmp_to_key(lambda a, b: 1.5)(2), failed(lambda: functools.cmp_to_key(lambda a, b: "x")(1) < functools.cmp_to_key(lambda a, b: "x")(2)), failed(lambda: functools.cmp_to_key(lambda a, b: "x")(1) == 1))  # type: ignore[arg-type,attr-defined,call-arg,misc,return-value]
k = K(1)
k.obj = 5  # type: ignore[attr-defined]
print(k.obj, K.__text_signature__ if False else 0)  # type: ignore[attr-defined]
del k.obj  # type: ignore[attr-defined]
print(k.obj, failed(lambda: k < K(1)), failed(lambda: K(1) < k), sorted(["b", "a"], key=functools.cmp_to_key(lambda a, b: (a > b) - (a < b))))  # type: ignore[attr-defined,operator]

# ---- lru_cache
log = []  # type: ignore[var-annotated]


class Key:
    def __init__(self, n):  # type: ignore[no-untyped-def]
        self.n = n

    def __hash__(self):  # type: ignore[no-untyped-def]
        log.append("hash " + str(self.n))
        return self.n

    def __eq__(self, other):  # type: ignore[no-untyped-def]
        log.append("eq")
        return self.n == other.n

    def __repr__(self):  # type: ignore[no-untyped-def]
        return "Key(" + str(self.n) + ")"


class Dies:
    def __init__(self, name):  # type: ignore[no-untyped-def]
        self.name = name

    def __del__(self):  # type: ignore[no-untyped-def]
        log.append("dies " + self.name)


@functools.lru_cache(maxsize=2)
def bounded(*a, **k):  # type: ignore[no-untyped-def]
    log.append("call " + repr(a))
    return len(a)


@functools.lru_cache(maxsize=None)
def infinite(*a):  # type: ignore[no-untyped-def]
    log.append("call " + repr(a))
    return len(a)


@functools.lru_cache(maxsize=0)
def uncached(*a):  # type: ignore[no-untyped-def]
    log.append("call " + repr(a))
    return len(a)


@functools.lru_cache
def plain(a):  # type: ignore[no-untyped-def]
    return a * 2


@functools.lru_cache(typed=True)
def typed(a):  # type: ignore[no-untyped-def]
    log.append("call " + repr(a))
    return a


@functools.cache
def cached(a):  # type: ignore[no-untyped-def]
    log.append("call " + repr(a))
    return a


for f in (bounded, infinite, uncached):
    for args in ((1,), (2,), (1,), (3,), (2,), (1,), ("a",), ("a",), ((1, 2),), ((1, 2),), (1.0,), (True,)):
        f(*args)
    print(f.__name__, f.cache_info(), log)
    log.clear()
    f.cache_clear()
    print(f.cache_info(), f.__wrapped__.__name__, f.cache_parameters(), f.__qualname__, f.__module__, type(f).__name__, callable(f))
print(plain(2), plain(2), plain.cache_info(), typed(1), typed(1.0), typed(True), typed(1), typed.cache_info(), log, cached(1), cached(1), cached.cache_info(), cached.cache_parameters())
log.clear()
print(bounded(Key(1)), log)  # type: ignore[no-untyped-call]
log.clear()
print(bounded(Key(1)), log)  # type: ignore[no-untyped-call]
log.clear()
print(bounded(Key(1), a=2), log)  # type: ignore[no-untyped-call]
log.clear()
print(bounded(a=1), bounded(a=1), bounded(b=1), bounded(a=1, b=2), bounded(b=2, a=1), bounded.cache_info(), log)
log.clear()
bounded.cache_clear()
print(failed(lambda: bounded([])), failed(lambda: bounded({})), failed(lambda: infinite([])), uncached([]), failed(lambda: functools.lru_cache(maxsize="a")), failed(lambda: functools.lru_cache(maxsize=1.5)), functools.lru_cache(maxsize=-1)(add).cache_info(), functools.lru_cache(maxsize=True)(add).cache_info(), failed(lambda: functools.lru_cache(1)(1)), failed(lambda: functools._lru_cache_wrapper()), failed(lambda: functools._lru_cache_wrapper(max)), failed(lambda: functools._lru_cache_wrapper(1, 1, 1, 1)), failed(lambda: functools._lru_cache_wrapper(max, "a", 1, 1)), failed(lambda: functools._lru_cache_wrapper(max, 2**70, 1, 1)), failed(lambda: functools._lru_cache_wrapper(max, 1, 1, 1, 1)), failed(lambda: functools._lru_cache_wrapper(max, 1, 1, 1).cache_info()))  # type: ignore[arg-type,call-arg,call-overload]
log.clear()


@functools.lru_cache(maxsize=1)
def holds(k):  # type: ignore[no-untyped-def]
    return Dies(k)  # type: ignore[no-untyped-call]


holds("a")
log.append("held")
holds("b")
log.append("evicted a")
holds.cache_clear()
log.append("cleared")
print(log)
log.clear()


def raises(n, seen=[]):  # type: ignore[no-untyped-def]
    seen.append(n)
    if len(seen) < 3:
        raise ValueError(n)
    return n


wrapped = functools.lru_cache(maxsize=1)(raises)
print(failed(lambda: wrapped(1)), wrapped.cache_info(), failed(lambda: wrapped(1)), wrapped(1), wrapped(1), wrapped.cache_info())


@functools.lru_cache(maxsize=2)
def reenters(n):  # type: ignore[no-untyped-def]
    if n > 0:
        return reenters(n - 1) + 1
    return 0


print(reenters(4), reenters.cache_info(), reenters(4), reenters.cache_info())


class Holder:
    @functools.lru_cache(maxsize=None)
    def m(self, a):  # type: ignore[no-untyped-def]
        return a

    @functools.cache
    def n(self):  # type: ignore[no-untyped-def]
        return 1


h = Holder()
print(h.m(1), Holder.m(h, 1), Holder.m.cache_info(), h.n(), h.m.__func__ is Holder.m, Holder.__dict__["m"].__get__(None, Holder) is Holder.m, failed(lambda: Holder.__dict__["m"].__get__(None, None)), bounded.__copy__() is bounded, bounded.__deepcopy__({}) is bounded, bounded.__reduce__(), failed(lambda: bounded.__copy__(1)), failed(lambda: bounded.__deepcopy__()), failed(lambda: bounded.cache_info(1)), failed(lambda: bounded.cache_clear(1)), failed(lambda: bounded.nothing), bounded.__dict__ is not None, sorted(bounded.__dict__), hasattr(bounded, "__weakref__"))  # type: ignore[attr-defined,call-arg]
bounded.tag = 1  # type: ignore[attr-defined]
print(bounded.tag, failed(lambda: type("Z", (type(bounded),), {})))  # type: ignore[attr-defined]

# ---- what the module builds
print(functools.WRAPPER_ASSIGNMENTS, functools.WRAPPER_UPDATES, sorted(functools.__all__))


def source(a):  # type: ignore[no-untyped-def]
    """doc"""


source.attr = 1  # type: ignore[attr-defined]


def dest():  # type: ignore[no-untyped-def]
    pass


functools.update_wrapper(dest, source)
print(dest.__name__, dest.__doc__, dest.__qualname__, dest.__module__, dest.attr, dest.__wrapped__ is source)  # type: ignore[attr-defined]


@functools.wraps(source)
def decorated():  # type: ignore[no-untyped-def]
    pass


print(decorated.__name__, decorated.__doc__, decorated.__wrapped__ is source)


@functools.total_ordering
class Ordered:
    def __init__(self, n):  # type: ignore[no-untyped-def]
        self.n = n

    def __eq__(self, o):  # type: ignore[no-untyped-def]
        return self.n == o.n

    def __lt__(self, o):  # type: ignore[no-untyped-def]
        return self.n < o.n


print(Ordered(1) < Ordered(2), Ordered(1) > Ordered(2), Ordered(1) <= Ordered(1), Ordered(2) >= Ordered(1), sorted([k for k in Ordered.__dict__ if k in ("__gt__", "__le__", "__ge__", "__lt__")]), failed(lambda: functools.total_ordering(type("N", (), {}))))  # type: ignore[no-untyped-call,operator]


class CP:
    def __init__(self):  # type: ignore[no-untyped-def]
        self.count = 0

    @functools.cached_property
    def v(self):  # type: ignore[no-untyped-def]
        self.count += 1
        return self.count

    pm = functools.partialmethod(lambda self, a, b: (a, b), 1)


c = CP()  # type: ignore[no-untyped-call]
print(c.v, c.v, c.count, c.__dict__, type(CP.__dict__["v"]).__name__, c.pm(2), CP.pm(c, 3), failed(lambda: CP.__dict__["v"].__get__(1)), CP.v is CP.__dict__["v"], repr(CP.__dict__["pm"]).startswith("functools.partialmethod("))


@functools.singledispatch
def disp(a):  # type: ignore[no-untyped-def]
    return "default"


@disp.register(int)
def _(a):  # type: ignore[no-untyped-def]
    return "int"


@disp.register(str)
def _(a):  # type: ignore[no-untyped-def]
    return "str"


disp.register(float, lambda a: "float")
print(disp(1), disp("a"), disp(1.5), disp(None), disp(True), disp.dispatch(bool).__name__, sorted([t.__name__ for t in disp.registry]), failed(lambda: disp()), failed(lambda: disp.register(1)), disp.__wrapped__.__name__)  # type: ignore[attr-defined,call-arg,call-overload]


class SM:
    @functools.singledispatchmethod
    def m(self, a):  # type: ignore[no-untyped-def]
        return "default"

    @m.register(int)
    def _(self, a):  # type: ignore[no-untyped-def]
        return "int"


print(SM().m(1), SM().m("a"), SM.__dict__["m"].__class__.__name__)
