# clause: C-3-40
# spec: section 3
# status: P1
# source: dialect specification section 3, Objects/tupleobject.c, Objects/typeobject.c
"""Subclasses of tuple: what makes one, its attributes, which of the built-in's operations ask a subclass's override and
which read the items directly, and what comes back: an exact tuple, or the same object."""
# ruff: noqa: B015, B018, B023, B033, B905, F632, C405, C408, C409, C414, C416, C417, E721, PLW0129, RUF005, RUF015, UP018, UP031, UP037


def failed(f: object) -> str:
    try:
        f()  # type: ignore[operator]
    except Exception as exc:
        return type(exc).__name__
    return "no error"


class T(tuple):  # type: ignore[type-arg]
    pass


class Named(tuple):  # type: ignore[type-arg]
    def __repr__(self) -> str:
        return "Named" + tuple.__repr__(self)


class Slotless(tuple):  # type: ignore[type-arg]
    __slots__ = ()


class New(tuple):  # type: ignore[type-arg]
    def __new__(cls, a: int, b: int) -> "New":
        return tuple.__new__(cls, (a, b))

    def __init__(self, a: int, b: int) -> None:
        self.total = a + b


class Super(tuple):  # type: ignore[type-arg]
    def __new__(cls, *items: int) -> "Super":
        return super().__new__(cls, items)


class Init(tuple):  # type: ignore[type-arg]
    def __init__(self, items: object) -> None:
        self.seen = items


class Sub(T):
    pass


# ---- what makes one
print(T(), T(()), T((1, 2)), T([1, 2]), T("ab"), T({1: 2}), T(range(3)), T(T((1,))), T(x for x in []) if False else 0, type(T()).__name__, type(T((1,))).__name__, T((1,)) == (1,), (1,) == T((1,)), T() == (), () == T(), T() is T(), T(()) is T(()), isinstance(T(), tuple), issubclass(T, tuple), T.__base__ is tuple, T.__mro__[1] is tuple, Sub.__mro__[2] is tuple, type(Sub([1])).__name__, Sub([1]), New(1, 2), New(1, 2).total, Super(1, 2, 3), type(Super(1)).__name__, Init([1, 2]), Init([1, 2]).seen, Named([1]), repr(Named([1])), str(Named([1])))
t = T((1, 2, 3))
print(tuple.__new__(T), tuple.__new__(T, (1, 2)), tuple.__new__(T, [1, 2]), type(tuple.__new__(T)).__name__, tuple.__new__(tuple), tuple.__new__(tuple, [1]), tuple.__new__(tuple, (1,)), tuple.__new__(Sub, t), type(tuple.__new__(Sub, t)).__name__, T.__new__(T, [1]), type(T.__new__(T, [1])).__name__, T.__new__(Sub, [1]), type(T.__new__(Sub, [1])).__name__, T.__new__(tuple, [1]), type(T.__new__(tuple, [1])).__name__)
same = (1, 2)
print(tuple(same) is same, tuple(t) is t, tuple(t) == t, type(tuple(t)).__name__, T(t) is t, type(T(t)).__name__, Sub(t) == t, tuple.__new__(tuple, same) is same, tuple.__new__(T, same) is same, type(t[:]).__name__, t[:] is t, same[:] is same, t[0:] is t, type(t[1:]).__name__, t[1:], t[::-1], t[::2], t[0], t[-1], t[True], len(t), bool(t), bool(T()), not T(), list(t), sorted(t, reverse=True), sum(t), min(t), max(t), set(t) == {1, 2, 3}, dict(enumerate(t)), [*t], (*t,), {*t} == {1, 2, 3}, print(*t), t.count(1), t.index(2), t.index(2, 1), t.__getnewargs__(), type(t.__getnewargs__()[0]).__name__, hash(t) == hash((1, 2, 3)), {t: 1}[(1, 2, 3)], {(1, 2, 3): 1}[t], t in {(1, 2, 3)}, (1, 2, 3) in {t}, 1 in t, 9 in t, [x for x in t], type(iter(t)).__name__)  # type: ignore[attr-defined,index]
for x in t:
    print(x, end=" ")
a, b, c = t
d, *e = t
print(a, b, c, d, e, failed(lambda: t[5]), failed(lambda: t["a"]), failed(lambda: t.nothing), failed(lambda: T(1)), failed(lambda: T(None)), failed(lambda: T(1, 2)), failed(lambda: T(x=1)), failed(lambda: T([1], x=1)), failed(lambda: tuple.__new__()), failed(lambda: tuple.__new__(1)), failed(lambda: tuple.__new__(int)), failed(lambda: tuple.__new__(object)), failed(lambda: tuple.__new__(T, 1)), failed(lambda: tuple.__new__(T, 1, 2)), failed(lambda: tuple.__new__(T, x=1)), failed(lambda: tuple.__new__(tuple, 1, 2)), failed(lambda: New(1)), failed(lambda: New((1, 2))), failed(lambda: Slotless(1)))  # type: ignore[arg-type,attr-defined,call-arg,call-overload,type-var]

# ---- concatenation and repetition: an exact tuple comes back, a subclass's self never
print(type(t + (4,)).__name__, t + (4,), type((4,) + t).__name__, (4,) + t, type(t + t).__name__, t + t, type(t + ()).__name__, (t + ()) is t, (() + t) is t, type(() + t).__name__, type(T() + T()).__name__, type(t * 2).__name__, t * 2, 2 * t, type(t * 1).__name__, (t * 1) is t, (1 * t) is t, (same * 1) is same, (same + ()) is same, (() + same) is same, (same * 0) == (), type(t * 0).__name__, t * 0, type(T() * 5).__name__, type(5 * T()).__name__, type(() * 5).__name__, failed(lambda: t + [1]), failed(lambda: [1] + t), failed(lambda: t + 1), failed(lambda: 1 + t), failed(lambda: t * "a"), failed(lambda: t * 1.5), failed(lambda: t - t), failed(lambda: t / 2), failed(lambda: -t), failed(lambda: ~t), failed(lambda: t % 2), failed(lambda: t ** 2), failed(lambda: t < 1), failed(lambda: 1 < t))  # type: ignore[operator]
u = T((1,))
u += (2,)  # type: ignore[assignment]
v = T((1,))
v *= 2  # type: ignore[assignment]
print(type(u).__name__, u, type(v).__name__, v, t < (1, 2, 4), t > (1, 2), t <= t, t >= t, (1, 2, 4) > t, (1, 2) < t, t != (1, 2, 3), t == [1, 2, 3], [1, 2, 3] == t, t == T((1, 2, 3)), t == Sub((1, 2, 3)), Sub((1, 2, 3)) == t, t == Named((1, 2, 3)), tuple.__eq__(t, (1, 2, 3)), tuple.__eq__((1, 2, 3), t), tuple.__eq__(t, 1), tuple.__lt__(t, (9,)), tuple.__add__(t, (4,)), tuple.__add__((4,), t), tuple.__mul__(t, 2), tuple.__rmul__(t, 2), tuple.__len__(t), tuple.__getitem__(t, 0), tuple.__getitem__(t, slice(0, 1)), tuple.__contains__(t, 1), tuple.__hash__(t) == hash(t), tuple.__repr__(t), tuple.__repr__(Named((1,))), list(tuple.__iter__(t)), tuple.count(t, 1), tuple.index(t, 1), tuple.__getnewargs__(t), failed(lambda: tuple.__add__(t, [1])), failed(lambda: tuple.__add__(1, t)), failed(lambda: tuple.__len__(1)), failed(lambda: tuple.__getitem__([1], 0)), failed(lambda: tuple.__iter__(1)), failed(lambda: tuple.__repr__(1)), failed(lambda: tuple.count(1, 1)))  # type: ignore[arg-type,attr-defined,call-overload,comparison-overlap,operator]

# ---- attributes
t.x = 1  # type: ignore[attr-defined]
print(t.x, vars(t), t.__dict__, hasattr(t, "__dict__"), hasattr((), "__dict__"), "x" in dir(t), hasattr(T, "__weakref__"), hasattr(t, "__weakref__"), failed(lambda: setattr((), "x", 1)), failed(lambda: delattr(t, "y")), failed(lambda: t.y))  # type: ignore[attr-defined]
del t.x  # type: ignore[attr-defined]
print(failed(lambda: t.x), vars(t), hasattr(Slotless(), "__dict__"), failed(lambda: setattr(Slotless(), "x", 1)), failed(lambda: vars(Slotless())), failed(lambda: Slotless().__dict__), failed(lambda: type("Bad", (tuple,), {"__slots__": ("x",)})), type("Empty", (tuple,), {"__slots__": ()})().__class__.__name__, failed(lambda: type("Bad2", (T,), {"__slots__": ("x",)})), failed(lambda: type("X", (tuple, list), {})), failed(lambda: type("X", (list, tuple), {})), failed(lambda: type("X", (tuple, int), {})), failed(lambda: type("X", (tuple, dict), {})), failed(lambda: type("X", (tuple, str), {})), failed(lambda: type("X", (T, tuple), {})), type("X", (tuple, T), {}) if False else 0, type("Y", (Sub, T), {}).__mro__[3].__name__)  # type: ignore[attr-defined]
t.__dict__["z"] = 2
print(t.z, t.__dict__)  # type: ignore[attr-defined]
t.__dict__ = {"w": 3}
print(t.w, vars(t), failed(lambda: setattr(t, "__dict__", 1)))  # type: ignore[attr-defined]
del t.__dict__
print(vars(t))


class Weak(tuple):  # type: ignore[type-arg]
    __slots__ = ("__weakref__",)


print(failed(lambda: type("W", (tuple,), {"__slots__": ("__weakref__",)})), failed(lambda: type("W2", (tuple,), {"__slots__": ("__dict__",)})))

# ---- class attributes and methods of its own


class Point(tuple):  # type: ignore[type-arg]
    origin = (0, 0)
    __match_args__ = ("first", "second")

    def __new__(cls, a: int, b: int) -> "Point":
        return super().__new__(cls, (a, b))

    @property
    def first(self) -> int:
        return self[0]  # type: ignore[no-any-return]

    @property
    def second(self) -> int:
        return self[1]  # type: ignore[no-any-return]

    def norm(self) -> int:
        return sum([v * v for v in self])

    @classmethod
    def make(cls, a: int) -> "Point":
        return cls(a, a)

    def __repr__(self) -> str:
        return "Point(" + ", ".join([repr(v) for v in self]) + ")"


p = Point(3, 4)
print(p, p.first, p.second, p.norm(), Point.make(1), p.origin, p == (3, 4), hash(p) == hash((3, 4)), p + (5,), type(p + (5,)).__name__, p * 1 is p, type(p[:]).__name__, type(p * 2).__name__, f"{p}", "%s" % (p,), "%s %s" % p, str(p), repr(p), [p], (p,), {p: 1}, format(p), format(p, ""), failed(lambda: format(p, "x")), isinstance(p, Point), isinstance(p, tuple), issubclass(Point, tuple))

# ---- the operations that use the tuple's own items, whatever the subclass says


class Loud(tuple):  # type: ignore[type-arg]
    def __iter__(self) -> object:  # type: ignore[override]
        print("Loud.__iter__", end=" ")
        return iter([7, 8])

    def __len__(self) -> int:
        print("Loud.__len__", end=" ")
        return 99

    def __getitem__(self, i: object) -> object:  # type: ignore[override]
        print("Loud.__getitem__", end=" ")
        return "got"

    def __contains__(self, x: object) -> bool:
        print("Loud.__contains__", end=" ")
        return False

    def __eq__(self, other: object) -> bool:
        print("Loud.__eq__", end=" ")
        return True

    def __ne__(self, other: object) -> bool:
        print("Loud.__ne__", end=" ")
        return False

    def __lt__(self, other: object) -> bool:
        print("Loud.__lt__", end=" ")
        return True

    def __hash__(self) -> int:
        print("Loud.__hash__", end=" ")
        return 5

    def __repr__(self) -> str:
        return "Loud!"

    def __bool__(self) -> bool:
        print("Loud.__bool__", end=" ")
        return False

    def __add__(self, other: object) -> str:  # type: ignore[override]
        return "Loud.__add__"

    def __radd__(self, other: object) -> str:
        return "Loud.__radd__"

    def __mul__(self, other: object) -> str:  # type: ignore[override]
        return "Loud.__mul__"

    def __rmul__(self, other: object) -> str:  # type: ignore[override]
        return "Loud.__rmul__"

    def __getnewargs__(self) -> object:
        return "Loud.__getnewargs__"

    def count(self, x: object) -> str:  # type: ignore[override]
        return "Loud.count"

    def index(self, x: object) -> str:  # type: ignore[override]
        return "Loud.index"


def show(*args: object, **kwds: object) -> object:
    return args, kwds


loud = Loud((1, 2))
print(list(loud))
print(tuple(loud), type(tuple(loud)).__name__)
print(Loud(loud) == 1)
print([*loud])
print((*loud,))
print({*loud} == {7, 8})
print(show(*loud))
print(len(loud))
print(loud[0])
print(loud[:])
print(1 in loud)
print(loud == 1)
print(1 == loud)
print(loud != 1)
print(1 != loud)
print((1, 2) == loud)
print(loud == (1, 2))
print(loud < 1)
print(1 > loud)
print((1, 2) > loud)
print(hash(loud))
print({loud: 1}[loud])
print(repr(loud), str(loud), f"{loud}", "%s" % (loud,))
print(bool(loud), not loud)
print(loud + (1,), (1,) + loud, loud * 2, 2 * loud)
print(loud.count(1), loud.index(1), loud.__getnewargs__())
print(tuple.__len__(loud), tuple.__getitem__(loud, 0), tuple.__contains__(loud, 1), tuple.__eq__(loud, (1, 2)), tuple.__hash__(loud) == hash((1, 2)), tuple.__repr__(loud), list(tuple.__iter__(loud)), tuple.count(loud, 1), tuple.index(loud, 1), tuple.__add__(loud, (3,)), tuple.__add__((3,), loud), tuple.__mul__(loud, 2), tuple.__getnewargs__(loud), tuple.__lt__(loud, (9,)))  # type: ignore[attr-defined]
print("%s %s" % loud)
print("%d" % Loud((5,)))  # type: ignore[str-format]
print(isinstance(1, Loud((int, str))), issubclass(int, Loud((int, str))), isinstance("a", Loud((int,))))
print("abc".startswith(Loud(("a", "x"))), "abc".endswith(Loud(("c",))))
print(b"abc".startswith(Loud((b"a",))), b"abc".endswith(Loud((b"x",))))
try:
    raise ValueError(1)
except Loud((ValueError, TypeError)) as exc:  # type: ignore[misc]
    print(type(exc).__name__)
x, y = loud  # type: ignore[attr-defined]
print(x, y)
f, *g = loud  # type: ignore[attr-defined]
print(f, g)
for item in loud:  # type: ignore[attr-defined]
    print(item, end=" ")
print()
print(max(loud), min(loud), sum(loud), sorted(loud), list(reversed(loud)) if False else 0, any(loud), all(loud), list(zip(loud, loud)), list(map(str, loud)), list(enumerate(loud)), dict([Loud((1, 2))]), dict([(1, 2)], **{}), list(filter(None, loud)), failed(lambda: "".join(Loud(("a", "b")))), "".join(T(("a", "b"))), [].__add__([1]), len({*loud}), len([*loud]), bytes(Loud((1, 2))), bytearray(Loud((1, 2))))  # type: ignore[list-item]
print(reversed(Loud((1, 2))).__class__.__name__, list(reversed(Loud((1, 2)))))
print(sorted([Loud((1,)), Loud((2,))]) != 0)  # type: ignore[comparison-overlap]
print(sorted([T((2, 1)), T((1, 2))]), sorted([(2, 1), T((1, 2))]), [T((1,))] == [(1,)], ((1,),) == (T((1,)),), min(T((2,)), T((1,))), max((2,), T((1,))))


class Lt(tuple):  # type: ignore[type-arg]
    def __lt__(self, other: object) -> bool:
        print("Lt.__lt__", end=" ")
        return tuple.__gt__(self, other)  # type: ignore[operator]


print(sorted([Lt((1,)), Lt((2,)), Lt((3,))]))
print(sorted([(Lt((1,)), 1), (Lt((2,)), 2)]))
print(sorted([1, 2], key=lambda k: Lt((k,))), max([Lt((1,)), Lt((2,))]), min([Lt((1,)), Lt((2,))]))

# ---- what a function gets
def star(*args: object) -> object:
    return args, type(args).__name__


print(star(*T((1, 2))), star(*Named((1,))), star(1, *T((2,)), 3), star(*Sub((1,)), *T((2,))), star(*loud))
print(type("K", (T,), {"a": 1})((1,)).a, T.__name__, T.__qualname__, T.__module__, T.__doc__, T.__dict__["__module__"], "__dict__" in T.__dict__, "__weakref__" in T.__dict__, "__dict__" in Slotless.__dict__, Slotless.__slots__)
print(T((1, 2)).__class__.__name__)
