# clause: C-3-34
# spec: section 3 (the data model), section 6 (dict), section 9 (lifetimes)
# status: P1
# source: decision 2026-11-03 (a subclass of a built-in type is that type's object); enum's _EnumDict
"""An instance of a dict subclass is a dict: isinstance, the dict's methods, equality and repr take
it as one. The subclass's overrides are reached where CPython reaches them: d[k], d[k] = v, del,
in, len and iteration call them, dict.__getitem__ calls __missing__, and a class body stores
through the __setitem__ of a namespace __prepare__ made; update, {**d}, **d, copy and dict(d)
read the dict's own entries unless the subclass overrides __iter__, then keys() and __getitem__.
copy and | give a plain dict, fromkeys an instance of the subclass. The instance has attributes
of its own, and dies as subtype_dealloc then dict_dealloc release it: the slots, the instance
dict, then the entries, each key before its value."""


class Probe:
    def __init__(self, name: str) -> None:
        self.name = name

    def __del__(self) -> None:
        print("dies", self.name)

    def __repr__(self) -> str:
        return self.name


class Loud(dict):  # type: ignore[type-arg]  # a bare base: dict[...] is a generic alias, not this case
    def __getitem__(self, k: str) -> int:
        print("getitem", k)
        return dict.__getitem__(self, k)  # type: ignore[no-any-return]  # a bare dict base: its items are Any

    def __setitem__(self, k: str, v: int) -> None:
        print("setitem", k)
        dict.__setitem__(self, k, v)

    def __missing__(self, k: str) -> int:
        print("missing", k)
        return 0

    def __contains__(self, k: object) -> bool:
        print("contains", k)
        return dict.__contains__(self, k)

    def __len__(self) -> int:
        print("len")
        return dict.__len__(self)


d = Loud(a=1)
print("made:", d, type(d).__name__, isinstance(d, dict), d == {"a": 1})
d["b"] = 2
print(d["a"], d["zz"], d.get("a"), d.get("q"), "a" in d, len(d))
del d["b"]
print("keys:", list(d.keys()), "values:", list(d.values()))
x: dict[str, int] = {}
x.update(d)
print("update:", x, {**d}, (lambda **k: k)(**d))
c = d.copy()
print("copy:", type(c).__name__, c, "or:", type(d | {"c": 3}).__name__, d | {"c": 3})


class Iterating(dict):  # type: ignore[type-arg]  # a bare base: dict[...] is a generic alias, not this case
    def __iter__(self) -> object:  # type: ignore[override]  # no import here; an iterator
        print("iter")
        return dict.__iter__(self)

    def keys(self) -> object:  # type: ignore[override]  # no import here; a keys view
        print("keys")
        return dict.keys(self)

    def __getitem__(self, k: str) -> int:
        print("getitem", k)
        return dict.__getitem__(self, k)  # type: ignore[no-any-return]  # a bare dict base: its items are Any


it = Iterating(p=1, q=2)
y: dict[str, int] = {}
y.update(it)
print("update:", y)
print("merge:", {**it})  # type: ignore[dict-item]  # a mapping, through keys()
print("copy:", it.copy())


class Plain(dict):  # type: ignore[type-arg]  # a bare base: dict[...] is a generic alias, not this case
    pass


p = Plain({1: 2}, x=3)  # type: ignore[dict-item]  # mixed keys on purpose
print(p, type(p).__name__, Plain.fromkeys("ab", 0), type(Plain.fromkeys("ab")).__name__, p == {1: 2, "x": 3})
p.attr = 5  # type: ignore[attr-defined]  # an attribute of the instance's own
print("attribute:", p.attr, vars(p), len(p))  # type: ignore[attr-defined]  # as above

recorded: list[str] = []


class Recording(dict):  # type: ignore[type-arg]  # a bare base: dict[...] is a generic alias, not this case
    def __setitem__(self, k: str, v: object) -> None:
        recorded.append(k)
        dict.__setitem__(self, k, v)


class Meta(type):
    @classmethod
    def __prepare__(mcls, name: str, bases: tuple[type, ...], /, **kw: object) -> Recording:
        return Recording()


class Made(metaclass=Meta):
    a = 1

    def f(self) -> None:
        pass


print("class body stores:", [k for k in recorded if k[:2] != "__"], type(Made.__dict__).__name__)


class Slotted(dict):  # type: ignore[type-arg]  # a bare base: dict[...] is a generic alias, not this case
    __slots__ = ("s", "__dict__")


s = Slotted()
s["k"] = Probe("value")
s[Probe("key")] = 1
s.s = Probe("slot")  # type: ignore[attr-defined]  # the slot exists at runtime
s.attr = Probe("attribute")  # type: ignore[attr-defined]  # the instance dict __slots__ asks for
del s
print("end")
