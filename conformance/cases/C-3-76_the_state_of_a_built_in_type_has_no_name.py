# clause: C-3-76
# spec: section 3 (the object model: what a built-in type keeps for itself)
# status: P1
# source: Objects/enumobject.c (enumobject), Modules/_collectionsmodule.c (dequeobject), Objects/weakrefobject.c (PyWeakReference.hash),
#         Modules/_randommodule.c (RandomObject), Modules/_io/stringio.c (stringio), Objects/typeobject.c (type_new_slots),
#         Objects/object.c (_PyObject_GenericSetAttrWithDict, PyObject_GenericGetAttr)
"""What a built-in type keeps for its own work is a field of its C struct, and a field has no name: it is no attribute
of the object and nothing in the type's dict. A class that derives from the type may use any name for itself, as an
attribute, a slot, a property, a method or a class attribute, and the type's own work neither reads it nor goes through
the class's __setattr__, __delattr__ and __getattr__."""
import functools
import io
import itertools
import operator
import random
import re
import struct
import threading
import weakref
from collections import OrderedDict, defaultdict, deque
from collections.abc import Callable, Iterator


class Thing:
    def __hash__(self) -> int:
        return 7


THING = Thing()
# names a runtime that writes these types in Python might keep their state under
NAMES: list[tuple[str, object, tuple[str, ...]]] = [
    ("enumerate", enumerate("ab"), ("_count", "_it")),
    ("zip", zip("ab", "cd", strict=True), ("_its", "_strict")),
    ("map", map(str, "ab"), ("_func", "_its", "_strict")),
    ("filter", filter(None, "ab"), ("_func", "_it")),
    ("reversed", reversed([1, 2]), ("_index", "_seq")),
    ("itertools.count", itertools.count(), ("_cnt", "_long_cnt", "_long_step")),
    ("itertools.chain", itertools.chain("ab"), ("_active", "_source")),
    ("itertools.islice", itertools.islice("ab", 1), ("_cnt", "_it", "_next", "_step", "_stop")),
    ("itertools.groupby", itertools.groupby("ab"), ("_a_it", "_b_keyfunc", "_c_tgtkey", "_d_currkey", "_e_currvalue", "_f_currgrouper")),
    ("deque", deque("ab"), ("_a_items", "_b_start", "_c_maxlen", "_d_state")),
    ("defaultdict", defaultdict(list), ("_a_factory",)),
    ("OrderedDict", OrderedDict(a=1), ("_a_od",)),
    ("random.Random", random.Random(1), ("_index", "_state")),
    ("functools.partial", functools.partial(print, 1), ("_p_phcount",)),
    ("weakref.ref", weakref.ref(THING), ("_hash",)),
    ("io.StringIO", io.StringIO("ab"), ("_a_ok", "_b_closed", "_c_decoder", "_d_text", "_e_pos", "_h_writenl", "_i_readnl")),
    ("io.BytesIO", io.BytesIO(b"ab"), ("_a_buf", "_b_pos", "_c_string_size", "_d_exports")),
    ("struct.Struct", struct.Struct("<i"), ("_codes", "_length", "_little")),
    ("operator.itemgetter", operator.itemgetter(1), ("_item", "_nitems")),
    ("re.Pattern", re.compile("a"), ("_a_pattern", "_b_flags", "_c_groups", "_f_code")),
    ("property", property(), ("_prop_get", "_prop_set", "_prop_del", "_prop_doc", "_prop_name", "_getter_doc")),
    ("staticmethod", staticmethod(len), ("_sm_callable",)),
    ("threading.local", threading.local(), ("_a_self_reference",)),
    ("a lock", threading.Lock(), ("_a_locked",)),
]

print("---- no such attribute, and nothing in the type's dict")
for label, obj, names in NAMES:
    seen = [name for name in names if hasattr(obj, name) or any(name in vars(c) for c in type(obj).__mro__)]
    try:
        object.__getattribute__(obj, names[0])
        direct = "found by object.__getattribute__"
    except AttributeError:
        direct = "not found by object.__getattribute__"
    print(f"{label}: seen {seen}, {direct}")


print("---- a class's own attributes under those names")


class Page(enumerate[str]):
    """Rows with their numbers; the page keeps how many rows it was told to expect."""

    def __init__(self, rows: list[str], start: int = 0) -> None:
        self._count = len(rows)
        self._it = "the page's own"


page = Page(["a", "b", "c"], 1)
print("Page:", page._count, page._it, sorted(vars(page)), "| first", next(page), "| then", page._count, "| rest", list(page), "| at the end", page._count)
del page._count
try:
    del page._count
except AttributeError:
    print("Page: deleted once, and then there is none to delete")
print("Page:", sorted(vars(page)), "| after the end", list(page))


class Pairs(zip):  # type: ignore[type-arg]
    def __init__(self, *iterables: object, strict: bool = False) -> None:
        self._its = "mine"
        self._strict = "mine too"


pairs = Pairs([1, 2], "ab", strict=True)
print("Pairs:", pairs._its, pairs._strict, list(pairs))
try:
    list(Pairs([1, 2], "abc", strict=True))
except ValueError:
    print("Pairs: strict still means strict")


class Dice(random.Random):
    def __init__(self, seed: int) -> None:
        super().__init__(seed)
        self._state = "rolling"
        self._index = -1


dice = Dice(5)
plain = random.Random(5)
print("Dice:", dice._state, dice._index, [dice.randint(1, 6) for _ in range(5)] == [plain.randint(1, 6) for _ in range(5)], dice._state, dice._index)


class Line(deque[int]):
    def __init__(self, maxlen: int) -> None:
        super().__init__(maxlen=maxlen)
        self._a_items = "people"
        self._b_start = "the door"
        self._c_maxlen = "no limit"
        self._d_state = "open"


line = Line(3)
for i in range(5):
    line.append(i)
print("Line:", list(line), line.maxlen, line.popleft(), len(line), line._a_items, line._b_start, line._c_maxlen, line._d_state)


class Text(io.StringIO):
    def __init__(self, text: str) -> None:
        super().__init__(text)
        self._a_ok = False
        self._b_closed = True
        self._d_text = "another text"
        self._e_pos = 400


text = Text("one\ntwo\n")
print("Text:", repr(text.readline()), text.tell(), text.closed, repr(text.getvalue()), text._a_ok, text._b_closed, text._d_text, text._e_pos)


class Half(functools.partial[int]):
    pass


half = Half(int, "11", base=2)
half._p_phcount = 9  # type: ignore[attr-defined]
print("Half:", half(), half.func is int, half.args, half.keywords, half._p_phcount)  # type: ignore[attr-defined]


class Shelf(defaultdict[str, list[int]]):
    def __init__(self) -> None:
        super().__init__(list)
        self._a_factory = "books"


shelf = Shelf()
shelf["a"].append(1)
print("Shelf:", dict(shelf), shelf.default_factory is list, shelf._a_factory)

print("---- a slot, a property, a method and a class attribute under those names")


class IdRef(weakref.ref[Thing]):
    """The shape of a weak reference that hashes by identity: a slot of its own for the hash."""

    __slots__ = ("_hash",)
    _hash: int

    def __new__(cls, ob: Thing) -> IdRef:
        self = weakref.ref.__new__(cls, ob)
        self._hash = 1000
        return self

    def __hash__(self) -> int:
        return self._hash


ref = IdRef(THING)
print("IdRef:", hash(ref), weakref.ref.__hash__(ref), ref._hash, ref() is THING)


class Counted(enumerate[str]):
    _it = "a class attribute"

    @property
    def _count(self) -> str:
        return "a property"


counted = Counted("ab", 5)
print("Counted:", counted._count, counted._it, list(counted), counted._count)


class Mapped(map):  # type: ignore[type-arg]
    def _func(self) -> str:
        return "a method"

    def _its(self) -> str:
        return "another"


mapped = Mapped(str.upper, "ab")
print("Mapped:", mapped._func(), mapped._its(), list(mapped))

print("---- the type's own work asks nothing of the class's __setattr__, __delattr__ and __getattr__")
LOG: list[str] = []


class Loud(deque[int]):
    def __setattr__(self, name: str, value: object) -> None:
        LOG.append("set " + name)
        super().__setattr__(name, value)

    def __delattr__(self, name: str) -> None:
        LOG.append("del " + name)
        super().__delattr__(name)

    def __getattr__(self, name: str) -> object:
        LOG.append("missing " + name)
        raise AttributeError(name)


loud = Loud(maxlen=4)
loud.append(1)
loud.appendleft(0)
loud.extend([2, 3])
loud.rotate(1)
loud.note = "mine"
del loud.note
print("Loud:", list(loud), len(loud), loud.pop(), loud.maxlen, hasattr(loud, "nothing"), LOG)
loud.clear()
loud.extendleft([5, 6])
print("Loud:", list(reversed(loud)), loud.copy() == loud, LOG)


class LoudShelf(defaultdict[str, int]):
    def __getattr__(self, name: str) -> object:
        LOG.append("missing " + name)
        raise AttributeError(name)

    def __setattr__(self, name: str, value: object) -> None:
        LOG.append("set " + name)
        super().__setattr__(name, value)


del LOG[:]
bare = LoudShelf.__new__(LoudShelf)              # before any __init__: the field holds nothing
print("LoudShelf:", bare.default_factory, LOG)
bare.__init__(int)  # type: ignore[misc]
bare["a"] += 2
bare.default_factory = None
print("LoudShelf:", dict(bare), bare.default_factory, LOG)


class LoudCount(enumerate[str]):
    def __setattr__(self, name: str, value: object) -> None:
        LOG.append("set " + name)
        super().__setattr__(name, value)

    def __getattr__(self, name: str) -> object:
        LOG.append("missing " + name)
        raise AttributeError(name)


del LOG[:]
print("LoudCount:", list(LoudCount("ab")), LOG, hasattr(LoudCount("ab"), "_count"), LOG)

print("---- names given at run time")


def exercise(label: str, make: Callable[[], object], names: tuple[str, ...], use: Callable[[object], object]) -> None:
    obj = make()
    for name in names:
        setattr(obj, name, "mine: " + name)
    print(f"{label}: {use(obj)!r}, {[getattr(obj, name) for name in names] == ['mine: ' + name for name in names]}, {sorted(vars(obj)) == sorted(names)}")


class Chain(itertools.chain[str]):
    pass


class Slice(itertools.islice):  # type: ignore[type-arg]
    pass


class Counter(itertools.count):  # type: ignore[type-arg]
    pass


class Order(OrderedDict[str, int]):
    pass


class Bytes(io.BytesIO):
    pass


class Local(threading.local):
    pass


class Kept(filter):  # type: ignore[type-arg]
    pass


class Back(reversed):  # type: ignore[type-arg]
    pass


def first_three(obj: object) -> list[object]:
    assert isinstance(obj, Iterator)
    return list(itertools.islice(obj, 3))


exercise("Chain", lambda: Chain("ab", "cd"), ("_active", "_source"), first_three)
exercise("Slice", lambda: Slice("abcdef", 1, None, 2), ("_cnt", "_it", "_next", "_step", "_stop"), first_three)
exercise("Counter", lambda: Counter(10, 5), ("_cnt", "_long_cnt", "_long_step"), first_three)
exercise("Kept", lambda: Kept(str.isupper, "aBcDeF"), ("_func", "_it"), first_three)
exercise("Back", lambda: Back("abcd"), ("_index", "_seq"), first_three)
exercise("Order", lambda: Order(b=1, a=2), ("_a_od",), lambda o: (list(o.items()), o.popitem(last=False)) if isinstance(o, Order) else None)
exercise("Bytes", lambda: Bytes(b"abc"), ("_a_buf", "_b_pos", "_c_string_size", "_d_exports"),
         lambda b: (b.read(2), b.tell(), b.getvalue()) if isinstance(b, Bytes) else None)
exercise("Local", Local, ("_a_self_reference",), lambda o: sorted(vars(o)))
