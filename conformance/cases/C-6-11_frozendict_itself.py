# clause: C-6-11
# spec: section 6
# status: P1
# source: dialect specification section 6 (frozendict, PEP 814), Objects/dictobject.c
"""frozendict by itself: C-6-05 reaches it through the copy module, this one needs nothing imported.
Its constructors, repr, hash, views, the | operator with each operand kind, what it refuses, and a
subclass of it."""
# ruff: noqa: B018, B905, C408, C416, E721, PLR0124


def failed(f: object) -> str:
    try:
        f()  # type: ignore[operator]
    except Exception as exc:
        return type(exc).__name__
    return "no error"


# ---- construction
fd = frozendict({"b": 2, "a": 1})
print(fd, repr(fd), str(fd), len(fd), list(fd), bool(fd), bool(frozendict()), frozendict(), repr(frozendict()), type(fd).__name__, type(fd))
print(frozendict(a=1), frozendict({"a": 1}, b=2), frozendict([("a", 1), ("b", 2)]), frozendict([("a", 1)], a=2), frozendict(iter([("x", 1)])), frozendict({1: 2}.items()), frozendict(fd))
print(frozendict(fd) is fd, frozendict(fd, c=3) is fd, frozendict({}) is frozendict({}), frozendict.__new__(frozendict, fd) is fd, frozendict.__new__(frozendict, fd) == fd)
print(failed(lambda: frozendict(1, 2)), failed(lambda: frozendict(1)), failed(lambda: frozendict("ab")), failed(lambda: frozendict([1])), failed(lambda: frozendict([(1, 2, 3)])), failed(lambda: frozendict({[]: 1})), failed(lambda: frozendict([([], 1)])))  # type: ignore[arg-type,call-overload]


class Pairs:
    def keys(self) -> list[str]:
        return ["k1", "k2"]

    def __getitem__(self, k: str) -> str:
        return k + "!"


print(frozendict(Pairs()))


# ---- reading
print(fd["a"], fd.get("a"), fd.get("z"), fd.get("z", 0), "a" in fd, "z" in fd, failed(lambda: fd["z"]), list(fd.keys()), list(fd.values()), list(fd.items()), fd.keys(), fd.values(), fd.items(), type(fd.keys()).__name__, type(iter(fd)).__name__)
print("a" in fd.keys(), ("a", 1) in fd.items(), 1 in fd.values(), len(fd.keys()))
print(fd.__getitem__("a"), fd.__contains__("a"), fd.__len__(), fd.__repr__(), list(fd.__iter__()), fd.__eq__(fd), fd.__ne__(fd), fd.__eq__(1), fd.__lt__(fd), fd.copy() is fd, fd.__getnewargs__(), type(fd.__getnewargs__()[0]).__name__, list(reversed(fd)), list(fd.__reversed__()), type(reversed(fd)).__name__)  # type: ignore[attr-defined,operator]
print(list(reversed(fd.keys())), list(reversed(fd.values())), list(reversed(fd.items())), list(reversed({"p": 1, "q": 2})), type(reversed({})).__name__, type(reversed({}.values())).__name__, type(reversed({}.items())).__name__)
print(dict(fd), type(dict(fd)).__name__, {**fd}, [*fd], (lambda **k: k)(**fd), sorted(fd), min(fd), max(fd), list(enumerate(fd)), list(zip(fd, fd.values())), dict(fd.items()) == fd)  # type: ignore[arg-type]
print(frozendict[str, int], type(frozendict[str, int]).__name__, frozendict[str, int].__origin__, frozendict[str, int](a=1), isinstance(fd, frozendict), isinstance(fd, dict), isinstance({}, frozendict), issubclass(frozendict, dict), issubclass(dict, frozendict), frozendict.__mro__, frozendict.__name__, frozendict.__module__, frozendict.__qualname__, frozendict.__base__, frozendict.__bases__)  # type: ignore[attr-defined]


# ---- equal and hash
print(fd == frozendict(a=1, b=2), fd == {"a": 1, "b": 2}, {"a": 1, "b": 2} == fd, fd != {"a": 1}, fd == 1, frozendict() == {}, frozendict(a=1) == frozendict(a=2), failed(lambda: fd < fd), failed(lambda: fd < {}), failed(lambda: {} < fd))  # type: ignore[comparison-overlap,operator]
print(hash(frozendict()), hash(frozendict(a=1)) == hash(frozendict({"a": 1})), hash(frozendict(a=1, b=2)) == hash(frozendict(b=2, a=1)), hash(frozendict({1: 2})), hash(frozendict({1: 2, 3: 4})), hash(frozendict({(1, 2): (3, 4)})), hash(frozendict({1: frozendict({2: 3})})), hash(frozendict({None: None})) == hash(frozendict({None: None})), hash(frozendict({2**70: 2**71})))
print(failed(lambda: hash(frozendict(a=[1]))), failed(lambda: hash(frozendict(a={}))), failed(lambda: {frozendict(a=[1]): 1}), {fd: 1}[frozendict(a=1, b=2)], fd in {fd}, frozendict(a=1) in {frozendict(a=1): 0}, len({fd, frozendict(b=2, a=1)}), failed(lambda: {{}: 1}), failed(lambda: {}[{}]))  # type: ignore[index]


class CountedHash:
    count = 0

    def __hash__(self) -> int:
        CountedHash.count += 1
        return 7


cached = frozendict(a=CountedHash())
print(hash(cached) == hash(cached), hash(cached) == hash(cached), CountedHash.count)


# ---- the operator
d = {"x": 1}
empty = frozendict()
print(fd | {"c": 3}, type(fd | {"c": 3}).__name__, {"c": 3} | fd, type({"c": 3} | fd).__name__, fd | frozendict(c=3), type(fd | frozendict(c=3)).__name__, fd | {"a": 9}, {"a": 9} | fd, fd | fd, d)
print(empty | fd is fd, fd | empty is fd, fd | {} is fd, empty | empty is empty, empty | {} is empty, empty | {"a": 1}, {} | empty, type({} | empty).__name__, type({} | fd).__name__, fd.__or__({"z": 1}), fd.__ror__({"z": 1}), type(fd.__ror__({"z": 1})).__name__, fd.__or__(1), fd.__ror__(1))  # type: ignore[operator]
print(failed(lambda: fd | 1), failed(lambda: 1 | fd), failed(lambda: fd | [("a", 1)]), failed(lambda: [] | fd))  # type: ignore[operator]
g = fd
g |= {"c": 3}
print(g, fd, g is fd, type(g).__name__)
h = {"a": 0}
h |= fd
print(h, type(h).__name__, fd.__class__, hasattr(fd, "__ior__"))
h.update(fd)
print(h)


# ---- what it refuses
def setit() -> None:
    fd["c"] = 3  # type: ignore[index]


def delit() -> None:
    del fd["a"]  # type: ignore[attr-defined]


print(failed(setit), failed(delit), fd)
for name in ("update", "pop", "popitem", "clear", "setdefault", "__setitem__", "__delitem__", "__ior__", "__init_subclass__", "__dict__", "fromkeys", "copy", "__class_getitem__", "__getnewargs__", "__hash__", "__or__", "__ror__", "__reversed__"):
    print(name, hasattr(fd, name), hasattr(frozendict, name))
print(failed(lambda: dict.__setitem__(fd, "c", 3)), failed(lambda: dict.update(fd, {})), failed(lambda: dict.get(fd, "a")), failed(lambda: frozendict.get({}, "a")), failed(lambda: setattr(fd, "x", 1)), failed(lambda: setattr(frozendict, "x", 1)), failed(lambda: frozendict.copy({})))  # type: ignore[ arg-type,call-overload,index]


class Holder:
    pass


def set_namespace() -> None:
    Holder().__dict__ = frozendict()  # type: ignore[assignment]


print(failed(set_namespace), failed(lambda: type("N", (), frozendict())), failed(lambda: type("N", (dict, frozendict), {})), failed(lambda: type("N", (frozendict, int), {})))  # type: ignore[call-overload]


class Prepared(type):
    @classmethod
    def __prepare__(mcs, name: str, bases: tuple[type, ...], /, **kw: object) -> frozendict[str, object]:  # type: ignore[override]
        return frozendict()


def prepared() -> None:
    class C(metaclass=Prepared):
        pass


print(failed(prepared))


# ---- fromkeys
print(frozendict.fromkeys("ab"), frozendict.fromkeys("ab", 0), type(frozendict.fromkeys("ab")).__name__, frozendict.fromkeys(fd), frozendict.fromkeys({"p": 1}, 2), frozendict.fromkeys({"p"}, 2), frozendict.fromkeys(frozenset({"q"})), dict.fromkeys(fd), type(dict.fromkeys(fd)).__name__, frozendict.fromkeys([]), failed(lambda: frozendict.fromkeys(1)), failed(lambda: frozendict.fromkeys([[]])), failed(lambda: frozendict.fromkeys()))  # type: ignore[call-overload]


# ---- a subclass
class F(frozendict[str, int]):
    tag = "F"

    def double(self) -> dict[str, int]:
        return {k: v * 2 for k, v in self.items()}


class Own(frozendict[str, int]):
    def __new__(cls, *args: object, **kw: int) -> Own:
        print("Own.__new__", args, kw)
        return super().__new__(cls, *args, **kw)  # type: ignore[return-value]

    def __init__(self, *args: object, **kw: int) -> None:
        print("Own.__init__", args, kw)

    def __repr__(self) -> str:
        return "Own<" + super().__repr__() + ">"

    def __hash__(self) -> int:
        return 5

    def __getitem__(self, k: str) -> int:
        return 100

    def __contains__(self, k: object) -> bool:
        return False

    def __iter__(self):  # type: ignore[no-untyped-def]
        return iter(["i"])

    def __len__(self) -> int:
        return 9

    def __eq__(self, other: object) -> bool:
        return True

    def __or__(self, other: object) -> str:  # type: ignore[override]
        return "or"

    def __ror__(self, other: object) -> str:  # type: ignore[override]
        return "ror"

    def __missing__(self, k: str) -> str:
        return "unreachable"


class Missing(frozendict[str, int]):
    def __missing__(self, k: str) -> str:
        return "missing " + k


f = F(a=1)
print(f, repr(f), type(f).__name__, f.tag, f.double(), f["a"], f == frozendict(a=1), frozendict(a=1) == f, hash(f) == hash(frozendict(a=1)), isinstance(f, frozendict), isinstance(f, dict), F.__mro__, F(), bool(F()), len(f), list(f), F.__base__)
print(frozendict(f) is f, type(frozendict(f)).__name__, type(f.copy()).__name__, f.copy() is f, f.copy() == f, type(f | {"b": 2}).__name__, type({"b": 2} | f).__name__, type(f | F(b=2)).__name__, type(frozendict(b=2) | f).__name__, f | frozendict() is f, frozendict() | f is f, type(frozendict() | f).__name__, f | {} is f)
f.note = "n"  # type: ignore[attr-defined]
print(f.note, f.__dict__, F.fromkeys("a"), type(F.fromkeys("a")).__name__, failed(lambda: F.fromkeys([[]])))  # type: ignore[attr-defined]
o = Own({"a": 1})
print(repr(o), str(o), hash(o), o["a"], "a" in o, list(o), len(o), o == 1, 1 == o, o | {}, {} | o, bool(o), dict(o), {**o}, list(o.keys()), list(o.items()), frozendict(o), type(frozendict(o)).__name__, frozendict.__hash__(o) == hash(frozendict(a=1)), frozendict.__repr__(o), frozendict.__len__(o), frozendict.__getitem__(o, "a"), frozendict.__contains__(o, "a"), list(frozendict.__iter__(o)), frozendict.__eq__(o, frozendict(a=1)), frozendict.__or__(o, {"b": 2}), frozendict.copy(o), type(frozendict.copy(o)).__name__)
print(Own.fromkeys("a"), Missing(a=1)["z"], Missing(a=1)["a"], Missing().get("z"), failed(lambda: frozendict()["z"]), "z" in Missing())
print(failed(lambda: F(a=1).update({})), failed(lambda: F(a=1).__setitem__("a", 1)), failed(lambda: frozendict.__init__(frozendict(), 1)), frozendict.__init__ is object.__init__, frozendict.__doc__ is not None, F.__doc__)  # type: ignore[attr-defined,call-arg,index]


class Stores(frozendict[str, int]):
    def __setitem__(self, k: str, v: int) -> None:
        print("stored", k, v)

    def __delitem__(self, k: str) -> None:
        print("deleted", k)


s = Stores()
s["a"] = 1
del s["b"]
print(s, Stores.fromkeys("a"), len(s))
