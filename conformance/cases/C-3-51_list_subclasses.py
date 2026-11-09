# clause: C-3-51
# spec: section 3
# status: P1
# source: dialect specification section 3, Objects/listobject.c, Objects/typeobject.c, Python/ceval.c
"""Subclasses of list: what makes one (list.__new__ ignores its arguments, list.__init__ refills), its attributes (a dict and a
weak reference slot of its own, __slots__ allowed), which of the built-in's operations ask a subclass's override and which read
the items directly, what comes back (an exact list, or the same object for the in-place operators), the mutating methods on a
subclass, and copy's reconstruction through the subclass's append."""
# ruff: noqa: B015, B018, B023, B033, B905, C405, C408, C409, C414, C416, C417, E501, E721, PLW0129, RUF005, RUF015, UP018, UP031, UP037
import copy
import weakref


def failed(f: object) -> str:
    try:
        f()  # type: ignore[operator]
    except Exception as exc:
        return type(exc).__name__
    return "no error"


class L(list):  # type: ignore[type-arg]
    pass


class Sub(L):
    pass


class Slots(list):  # type: ignore[type-arg]
    __slots__ = ("x",)


class Slotless(list):  # type: ignore[type-arg]
    __slots__ = ()


class New(list):  # type: ignore[type-arg]
    def __new__(cls, *args: object, **kwds: object) -> "New":
        return super().__new__(cls)


class Init(list):  # type: ignore[type-arg]
    def __init__(self, a: int, b: int) -> None:
        super().__init__([a, b])
        self.total = a + b


# ---- what makes one
print(L(), L([]), L([1, 2]), L((1, 2)), L("ab"), L({1: 2}), L(range(3)), L(L([1])), L(x for x in [5, 6]), type(L()).__name__, type(L([1])).__name__, L([1]) == [1], [1] == L([1]), L() == [], L() is L(), isinstance(L(), list), issubclass(L, list), L.__base__ is list, L.__mro__[1] is list, Sub.__mro__[2] is list, type(Sub([1])).__name__, Init(1, 2), Init(1, 2).total, type(Init(1, 2)).__name__)
print(list.__new__(L), type(list.__new__(L)).__name__, list.__new__(L, [1, 2]), list.__new__(L, 1, 2), list.__new__(list, [1]), L.__new__(Sub), type(L.__new__(Sub)).__name__, New([1, 2]), New([1], x=1), failed(lambda: L(1)), failed(lambda: L(None)), failed(lambda: L(1, 2)), failed(lambda: L(x=1)), failed(lambda: L([1], x=1)), failed(lambda: New(1, 2)), failed(lambda: list.__new__(int)), failed(lambda: list.__new__()), failed(lambda: list.__init__(1)), failed(lambda: list.__init__(L(), 1, 2)))  # type: ignore[call-arg,call-overload]
r = L([1, 2])
r.__init__([3])  # type: ignore[misc]
print(r)
r.__init__()  # type: ignore[misc]
print(r)
list.__init__(r, "xy")
print(r, type(r).__name__)

# ---- reading it
s = L([3, 1, 2])
print(len(s), bool(s), bool(L()), not L(), s[0], s[-1], s[True], s[:], type(s[:]).__name__, s[1:], type(s[::-1]).__name__, s[::2], 1 in s, 9 in s, list(s), type(list(s)).__name__, tuple(s), sorted(s), type(sorted(s)).__name__, sum(s), min(s), max(s), set(s) == {1, 2, 3}, dict(enumerate(s)), [*s], (*s,), {*s} == {1, 2, 3}, s.count(1), s.index(2), [x for x in s], type(iter(s)).__name__, list(reversed(s)), type(reversed(s)).__name__, failed(lambda: hash(s)), failed(lambda: {s: 1}), s == [3, 1, 2], s != [3, 1, 2], s < [4], s > [3, 1], s <= s, s == (3, 1, 2), s == L([3, 1, 2]), s == Sub([3, 1, 2]))  # type: ignore[comparison-overlap]
for item in s:
    print(item, end=" ")
a, b, c = s
d, *e = s
print(a, b, c, d, e, failed(lambda: s[5]), failed(lambda: s["a"]), failed(lambda: s.nothing), "%s" % s, "%s" % (s,), f"{s}", str(s), repr(s), format(s), [s], (s,))  # type: ignore[attr-defined,call-overload]

# ---- what comes back: an exact list, or self for the in-place operators
t = L([1, 2])
print(type(t + [3]).__name__, t + [3], type([3] + t).__name__, type(t + t).__name__, type(t * 2).__name__, t * 2, 2 * t, type(t * 1).__name__, (t * 1) is t, type(t.copy()).__name__, t.copy(), type(copy.copy([1])).__name__, failed(lambda: t + (3,)))  # type: ignore[operator]
u = t
u += [3]
print(u is t, type(u).__name__, u)
u += (4,)
print(u is t, u)
u *= 2
print(u is t, type(u).__name__, u)
u *= 0
print(u is t, u)

# ---- the mutating methods on a subclass
m = L([5, 3, 4])
m.append(1)
m.extend([2, 2])
m.extend(L([0]))
m.insert(0, 9)
print(m, m.pop(), m.pop(0), m)
m.remove(2)
m.sort()
print(m)
m.sort(key=lambda v: -v, reverse=True)
print(m)
m.reverse()
m[0] = 7
m[1:3] = [8, 8, 8]
del m[0]
del m[::2]
print(m, type(m).__name__)
m.clear()
print(m, len(m), type(m).__name__, failed(lambda: m.pop()), failed(lambda: m.remove(1)), failed(lambda: m.index(1)))

# ---- attributes
t.x = 1  # type: ignore[attr-defined]
print(t.x, vars(t), t.__dict__, hasattr(t, "__dict__"), hasattr([], "__dict__"), "x" in dir(t), hasattr(L, "__weakref__"), "__weakref__" in L.__dict__, "__dict__" in L.__dict__, weakref.ref(t)() is t, failed(lambda: weakref.ref([])), failed(lambda: setattr([], "x", 1)), failed(lambda: delattr(t, "y")))  # type: ignore[attr-defined]
del t.x  # type: ignore[attr-defined]
t.__dict__ = {"w": 3}
print(failed(lambda: t.x), t.w, vars(t))  # type: ignore[attr-defined]
sl = Slots([1])
sl.x = 5  # type: ignore[attr-defined]
print(sl.x, sl, failed(lambda: setattr(sl, "y", 1)), failed(lambda: vars(sl)), hasattr(Slots, "__weakref__"), failed(lambda: setattr(Slotless(), "x", 1)), failed(lambda: weakref.ref(Slotless())), Slots.__slots__, "__dict__" in Slots.__dict__)  # type: ignore[attr-defined]


class Stack(list):  # type: ignore[type-arg]
    kind = "stack"

    def push(self, v: int) -> "Stack":
        self.append(v)
        return self

    @property
    def top(self) -> int:
        return self[-1]  # type: ignore[no-any-return]

    def __repr__(self) -> str:
        return "Stack" + list.__repr__(self)


st = Stack().push(1).push(2)
print(st, st.top, st.kind, len(st), str(st), f"{st}", [st], "%s" % st, st + [3], type(st + [3]).__name__, Stack.__name__, Stack.__qualname__, Stack.__module__, Stack.__doc__, Stack.__dict__["__module__"], L[int], type(L[int]).__name__)  # type: ignore[misc]

# ---- the operations that ask an override, and those that read the items


class Loud(list):  # type: ignore[type-arg]
    def __iter__(self) -> object:  # type: ignore[override]
        print("Loud.__iter__", end=" ")
        return iter([7, 8])

    def __len__(self) -> int:
        print("Loud.__len__", end=" ")
        return 99

    def __getitem__(self, i: object) -> object:  # type: ignore[override]
        print("Loud.__getitem__", end=" ")
        return "got"

    def __setitem__(self, i: object, v: object) -> None:
        print("Loud.__setitem__", end=" ")

    def __delitem__(self, i: object) -> None:
        print("Loud.__delitem__", end=" ")

    def __contains__(self, x: object) -> bool:
        print("Loud.__contains__", end=" ")
        return False

    def __eq__(self, other: object) -> bool:
        print("Loud.__eq__", end=" ")
        return True

    def __lt__(self, other: object) -> bool:
        print("Loud.__lt__", end=" ")
        return True

    def __repr__(self) -> str:
        return "Loud!"

    def __bool__(self) -> bool:
        print("Loud.__bool__", end=" ")
        return False

    def __add__(self, other: object) -> str:  # type: ignore[override]
        return "Loud.__add__"

    def __iadd__(self, other: object) -> str:  # type: ignore[override]
        return "Loud.__iadd__"

    def __mul__(self, other: object) -> str:  # type: ignore[override]
        return "Loud.__mul__"

    def __reversed__(self) -> object:  # type: ignore[override]
        print("Loud.__reversed__", end=" ")
        return iter([0])

    def append(self, x: object) -> None:
        print("Loud.append", end=" ")

    def extend(self, x: object) -> None:
        print("Loud.extend", end=" ")


def show(*args: object) -> object:
    return args


loud = Loud([1, 2])
print(list(loud))
print(tuple(loud))
print([*loud])
print((*loud,))
print({*loud} == {7, 8})
print(show(*loud))
print(len(loud))
print(loud[0])
loud[0] = 5
print(list.__getitem__(loud, 0))
del loud[0]
print(list.__len__(loud))
print(1 in loud)
print(loud == 1, 1 == loud, loud != 1, [1, 2] == loud, loud == [1, 2])
print(loud < 1, [9] > loud)
print(repr(loud), str(loud), f"{loud}", "%s" % loud)
print(bool(loud), not loud)
print(loud + [1], [1] + loud, loud * 2)
lo = loud
lo += [3]  # type: ignore[misc]
print(lo)
print(list(reversed(loud)))  # type: ignore[call-overload]
x, y = loud  # type: ignore[attr-defined]
print(x, y)
f, *g = loud  # type: ignore[attr-defined]
print(f, g)
for item in loud:  # type: ignore[attr-defined]
    print(item, end=" ")
print()
print(max(loud), min(loud), sum(loud), sorted(loud), any(loud), all(loud), list(zip(loud, loud)), list(map(str, loud)), list(enumerate(loud)), list(filter(None, loud)), dict(L([(1, 2)])), failed(lambda: "".join(Loud(["a", "b"]))), "".join(L(["a", "b"])))
print(list.__len__(loud), list.__getitem__(loud, 0), list.__contains__(loud, 2), list.__eq__(loud, [2]), list.__repr__(loud), list(list.__iter__(loud)), list.count(loud, 2), list.index(loud, 2), list.__add__(loud, [3]), list.__mul__(loud, 2), list(list.__reversed__(loud)), loud.copy(), type(loud.copy()).__name__)
target = [0]
target.extend(loud)
print(target)
target += loud
print(target)
target[1:2] = loud
print(target)
listed: list[object] = []
listed[:] = Loud([1, 2, 3])
print(listed, [0, *loud, 9], list.__init__(Loud([1]), loud) is None)
loud.sort()
print(list.__repr__(loud))


class Lt(list):  # type: ignore[type-arg]
    def __lt__(self, other: object) -> bool:
        print("Lt.__lt__", end=" ")
        return list.__gt__(self, other)  # type: ignore[operator]


print(sorted([Lt([1]), Lt([2]), Lt([3])]))
print(max([Lt([1]), Lt([2])]), min([Lt([1]), Lt([2])]))

# ---- copy reconstructs through the subclass's append and extend


class Logged(list):  # type: ignore[type-arg]
    def append(self, v: object) -> None:
        print("Logged.append", v, end=" ")
        super().append(v)

    def extend(self, v: object) -> None:
        print("Logged.extend", end=" ")
        super().extend(v)  # type: ignore[arg-type]


lg = Logged([1, [2]])
lg.tag = "t"  # type: ignore[attr-defined]
c1 = copy.copy(lg)
print(type(c1).__name__, c1, c1.tag, c1[1] is lg[1])  # type: ignore[attr-defined]
c2 = copy.deepcopy(lg)
print(type(c2).__name__, c2, c2.tag, c2[1] is lg[1])  # type: ignore[attr-defined]
rx = lg.__reduce_ex__(2)
print(rx[0].__name__, rx[1], rx[2], list(rx[3]), rx[4], lg.__reduce__()[0].__name__, lg.__reduce__()[1][1:])  # type: ignore[union-attr]
print(copy.copy(Slots([4])), copy.deepcopy(L([[1]])), type(copy.deepcopy(L([[1]]))).__name__)
