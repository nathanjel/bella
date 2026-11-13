# clause: C-3-71
# spec: section 3 (the data model: iterators), section 6 (builtins: iter, reversed, enumerate, zip, map, filter)
# status: P1
# source: Objects/listobject.c (listiter_len, listiter_reduce_general, listiter_setstate and the reverse iterator's), Objects/tupleobject.c
#         (tupleiter_*), Objects/rangeobject.c (range_iterator, longrange_iterator), Objects/unicodeobject.c (unicodeiter_*),
#         Objects/bytesobject.c (striter_*), Objects/bytearrayobject.c (bytearrayiter_*), Objects/dictobject.c (dictiter_len,
#         dictiter_reduce), Objects/setobject.c (setiter_*), Objects/iterobject.c (iter_*, calliter_reduce), Objects/enumobject.c
#         (enum_reduce, reversed_*), Python/bltinmodule.c (filter_reduce, map_reduce, map_setstate, zip_reduce, zip_setstate)
"""What a built-in iterator answers about itself. `__length_hint__` is how many items it expects still to give (what
operator.length_hint asks); `__reduce__` is the call that makes an iterator like it, with where it stands as the state, or as
the argument where the type keeps no index (a range's iterator is a shorter range, a dict's or a set's is a list of what is
left); `__setstate__` moves it, clipped to its sequence. So copy.copy and copy.deepcopy make an iterator that goes on from
the same place. An exhausted iterator has let go of its sequence and stays exhausted; one that was only moved off its
sequence has not, and can be moved back."""
import copy
import operator
import sys
import weakref
from collections.abc import Callable, Iterator

NAMES = ("__length_hint__", "__reduce__", "__setstate__")


class Seq:
    """The old protocol: __getitem__ from 0 until IndexError, and no length."""

    def __getitem__(self, index: int) -> int:
        if index >= 3:
            raise IndexError
        return index * 10

    def __repr__(self) -> str:
        return type(self).__name__ + "()"


class Sized(Seq):
    def __len__(self) -> int:
        return 3


class Asked(Seq):
    """A length that says when it was asked."""

    def __init__(self) -> None:
        self.asked = 0

    def __len__(self) -> int:
        self.asked += 1
        return 3


class Lengthless(Seq):
    def __len__(self) -> int:
        raise ZeroDivisionError


class Index:
    def __index__(self) -> int:
        return 1


class Unbool:
    def __bool__(self) -> bool:
        raise ZeroDivisionError


class Items(list):  # type: ignore[type-arg]
    pass


class Text(str):
    pass


class E(enumerate):  # type: ignore[type-arg]
    pass


class Z(zip):  # type: ignore[type-arg]
    pass


class M(map):  # type: ignore[type-arg]
    pass


class F(filter):  # type: ignore[type-arg]
    pass


class R(reversed):  # type: ignore[type-arg]
    pass


def attempt(thunk: Callable[[], object]) -> str:
    try:
        result = thunk()
    except Exception as exc:  # noqa: BLE001  # which exception, by class
        return type(exc).__name__
    return ascii(result)


def shape(value: object) -> object:
    """A value as it can be printed: an iterator or a callable by its type's name, a list or a bytearray as it is now."""
    if isinstance(value, tuple):
        return tuple(shape(v) for v in value)
    if type(value) is list:
        return list(value)
    if type(value) is bytearray:
        return bytearray(value)
    if hasattr(type(value), "__next__") or callable(value):
        return "<" + type(value).__name__ + ">"
    return value


def hint(it: object) -> object:
    return it.__length_hint__()  # type: ignore[attr-defined]


def reduced(it: object) -> tuple[object, ...]:
    """__reduce__(): the callable by its name, then its arguments and the state if there is one."""
    made = it.__reduce__()
    assert isinstance(made, tuple)
    return (made[0].__name__, *(shape(part) for part in made[1:]))


def move(it: object, state: object) -> object:
    return it.__setstate__(state)  # type: ignore[attr-defined]


MAKERS: list[tuple[str, Callable[[], Iterator[object]]]] = [
    ("a list's", lambda: iter([1, 2, 3])),
    ("a list's, reversed", lambda: reversed([1, 2, 3])),
    ("a tuple's", lambda: iter((1, 2, 3))),
    ("a range's", lambda: iter(range(0, 10, 3))),
    ("a range's, reversed", lambda: reversed(range(0, 10, 3))),
    ("a long range's", lambda: iter(range(2 ** 70, 2 ** 70 + 3))),
    ("a str's", lambda: iter("abc")),
    ("a str's beyond ASCII", lambda: iter("ażc")),
    ("a bytes's", lambda: iter(b"abc")),
    ("a bytearray's", lambda: iter(bytearray(b"abc"))),
    ("a dict's", lambda: iter({1: 2, 3: 4, 5: 6})),
    ("a dict's values'", lambda: iter({1: 2, 3: 4, 5: 6}.values())),
    ("a dict's items'", lambda: iter({1: 2, 3: 4, 5: 6}.items())),
    ("a dict's, reversed", lambda: reversed({1: 2, 3: 4, 5: 6})),
    ("a dict's values', reversed", lambda: reversed({1: 2, 3: 4, 5: 6}.values())),
    ("a dict's items', reversed", lambda: reversed({1: 2, 3: 4, 5: 6}.items())),
    ("a set's", lambda: iter({1, 2, 3})),
    ("a frozenset's", lambda: iter(frozenset({1, 2, 3}))),
    ("the old protocol's", lambda: iter(Seq())),
    ("the old protocol's, with a length", lambda: iter(Sized())),
    ("reversed()", lambda: reversed(Sized())),
]

for label, make in MAKERS:
    it = make()
    kind = type(it)
    print(label + ":", kind.__name__, [n for n in NAMES if n in vars(kind)], sorted({type(vars(kind)[n]).__name__ for n in NAMES if n in vars(kind)}),
          vars(kind)["__doc__"] is None or kind is reversed, it.__doc__ is None or kind is reversed, type(it.__reduce__).__name__)
    print("    fresh:", hint(it), operator.length_hint(it), reduced(it))
    first = next(it)
    print("    after one:", first, hint(it), operator.length_hint(it, 7), reduced(it))
    twin, deep = copy.copy(it), copy.deepcopy(it)
    print("    copies:", type(twin).__name__, type(deep).__name__, list(twin), list(deep), hint(it))
    rest = list(it)
    print("    exhausted:", rest, hint(it), operator.length_hint(it, 7), reduced(it), attempt(lambda it=it: next(it)), list(copy.copy(it)))  # type: ignore[misc]

STATES: tuple[object, ...] = (-5, -1, 0, 2, 3, 99, True, 2 ** 70, -2 ** 70, "2", 1.5, None, Index())


def moved(make: Callable[[], Iterator[object]], state: object, steps: int) -> str:
    """The iterator after `steps` calls of next(), moved to `state`: what __setstate__ said, and what is left."""
    it = make()
    for _ in range(steps):
        next(it, None)
    said = attempt(lambda: move(it, state))
    return said + " " + attempt(lambda: list(it))


for label, make in MAKERS:
    if "__setstate__" in vars(type(make())):
        print(label, "moved:", [moved(make, state, 0) for state in STATES])
        print(label, "moved after one:", [moved(make, state, 1) for state in (-1, 0, 1, 99)])
        print(label, "moved after three:", [moved(make, state, 3) for state in (0, 1)], moved(make, "x", 3))
        print(label, "moved after five:", [moved(make, state, 5) for state in (-1, 0, 1)], moved(make, "x", 5))

# moved off its sequence and back: the sequence is still held
forward = iter([1, 2, 3])
move(forward, -1)
print("a list's, off the front:", hint(forward), reduced(forward), list(forward), move(forward, 1), list(forward), move(forward, 0), list(forward))
backward = reversed([1, 2, 3])
print("a list's, reversed, to its end:", list(backward), hint(backward), reduced(backward), move(backward, 1), hint(backward), list(backward), move(backward, 99),
      list(backward))
shrunk = [1, 2, 3]
backward = reversed(shrunk)
shrunk.clear()
print("a list's, reversed, the list cut:", hint(backward), reduced(backward), attempt(lambda: next(backward)), move(backward, 0), shrunk.append(1), list(backward))  # type: ignore[func-returns-value]
grown = [1]
forward = iter(grown)
print("a list's, the list grown:", next(forward), hint(forward), grown.extend([2, 3]), hint(forward), reduced(forward), move(forward, 5), hint(forward), list(forward))  # type: ignore[func-returns-value]
bytewise = iter(bytearray(b"abc"))
move(bytewise, -1)
print("a bytearray's, off the front:", hint(bytewise), reduced(bytewise), list(bytewise), move(bytewise, 0), list(bytewise))
array = bytearray(b"abc")
bytewise = iter(array)
print("a bytearray's, the array cut:", next(bytewise), next(bytewise), array.clear(), hint(bytewise), reduced(bytewise), move(bytewise, 0), array.extend(b"xy"), list(bytewise))  # type: ignore[func-returns-value]
ranged = iter(range(10))
print("a range's, moved from where it stands:", next(ranged), move(ranged, 2), next(ranged), hint(ranged), move(ranged, Index()), next(ranged), reduced(ranged),
      move(ranged, 99), hint(ranged), reduced(ranged))
long_ranged = iter(range(2 ** 70, 2 ** 70 + 10, 2))
print("a long range's, moved from where it stands:", next(long_ranged) - 2 ** 70, move(long_ranged, 2), next(long_ranged) - 2 ** 70, hint(long_ranged),
      attempt(lambda: move(long_ranged, Index())), attempt(lambda: move(long_ranged, True)), move(long_ranged, 2 ** 80), hint(long_ranged), list(long_ranged))
huge = iter(range(0, 2 ** 100, 2 ** 70))
print("a long range's own length:", hint(huge) == 2 ** 30, attempt(lambda: operator.length_hint(iter(range(2 ** 100)))), hint(iter(range(2 ** 100))) == 2 ** 100)

# an exhausted reverse iterator of a list holds the list (it stands at -1, and can be moved back); a forward one has let go
held = Items([1, 2, 3])
watch = weakref.ref(held)
backward = reversed(held)
del held
print("held by the reverse iterator:", list(backward), watch() is None, move(backward, 0), list(backward), watch() is None)
backward = reversed([0])
held = Items([1, 2, 3])
watch_forward = weakref.ref(held)
forward = iter(held)
del held
print("let go by the forward one:", watch() is None, list(forward), watch_forward() is None)

# a dict's and a set's: the hint is the count while the size is what it was; __reduce__ lists what is left and leaves the iterator where it stood
table = {1: 2, 3: 4, 5: 6}
keys = iter(table)
print("a dict's, untouched by __reduce__:", next(keys), reduced(keys), reduced(keys), hint(keys), list(keys), hint(keys), reduced(keys))
keys = iter(table)
table[7] = 8
print("a dict's, the dict grown:", hint(keys), attempt(lambda: reduced(keys)), operator.length_hint(keys, 7))
del table[7]
print("a dict's, the size back:", hint(keys), reduced(keys), list(keys))
keys = iter(table)
table[7] = 8
print("a dict's, failed:", attempt(lambda: next(keys)), table.pop(7), hint(keys), attempt(lambda: reduced(keys)), attempt(lambda: next(keys)))
for view in (table.values(), table.items()):
    walker = iter(view)
    backwards = reversed(view)
    table[9] = 0
    print("a view's, the dict grown:", hint(walker), attempt(lambda walker=walker: reduced(walker)), hint(backwards), attempt(lambda backwards=backwards: reduced(backwards)))  # type: ignore[misc]
    del table[9]
    print("a view's, the size back:", hint(walker), reduced(walker), hint(backwards), reduced(backwards))
# a reverse iterator stands at an entry of the table: a table rebuilt shorter under it ends it, and one that puts an entry back under it fails it
packed = {1: 2, 3: 4, 5: 6}
for _ in range(2):
    packed[7] = 8
    del packed[7]
turned_keys = reversed(packed)
packed[9] = 0
del packed[9]
print("a dict's, reversed, the table rebuilt:", hint(turned_keys), reduced(turned_keys), list(turned_keys), hint(turned_keys), list(reversed(packed)))
packed = {1: 2, 7: 0, 9: 0, 3: 4, 5: 6}
del packed[7], packed[9]
turned_keys = reversed(packed)
print("a dict's, reversed, an entry put back under it:", next(turned_keys), next(turned_keys), packed.setdefault(11, 0), packed.pop(11), hint(turned_keys),
      attempt(lambda: reduced(turned_keys)), next(turned_keys), hint(turned_keys), attempt(lambda: reduced(turned_keys)), attempt(lambda: next(turned_keys)), attempt(lambda: next(turned_keys)), hint(turned_keys))
members = {1, 2, 3}
member = iter(members)
print("a set's, untouched by __reduce__:", next(member), reduced(member), reduced(member), hint(member))
members.add(4)
print("a set's, the set grown:", hint(member), attempt(lambda: reduced(member)), operator.length_hint(member, 7))
members.discard(4)
print("a set's, the size back:", hint(member), reduced(member), list(member), hint(member), reduced(member))

# the old protocol's iterator asks the sequence's length each time, and has none to give when the sequence has none
asked = Asked()
old = iter(asked)
print("the old protocol's, asking:", hint(old), asked.asked, next(old), hint(old), asked.asked, operator.length_hint(old), asked.asked, move(old, 7), hint(old), reduced(old),
      list(old), hint(old), asked.asked)
print("the old protocol's, no length:", hint(iter(Seq())), operator.length_hint(iter(Seq()), 7), attempt(lambda: hint(iter(Lengthless()))),
      attempt(lambda: operator.length_hint(iter(Lengthless()))), attempt(lambda: move(iter(Seq()), 2 ** 70)))
far = iter(Seq())
print("the old protocol's, as far as an index goes:", move(far, sys.maxsize), reduced(far) == ("iter", (Seq(),), sys.maxsize) or reduced(far)[2] == sys.maxsize,
      attempt(lambda: next(far)), attempt(lambda: next(far)), move(far, sys.maxsize - 1), attempt(lambda: next(far)), reduced(far), move(far, 0), list(far))
asked = Asked()
turned = reversed(asked)
print("reversed(), asking:", asked.asked, hint(turned), asked.asked, [next(turned), next(turned), next(turned)], hint(turned), asked.asked, reduced(turned), move(turned, 1),
      asked.asked, list(turned), attempt(lambda: hint(reversed(Lengthless()))))
turned = reversed(Asked())
print("reversed(), moved:", move(turned, 99), hint(turned), reduced(turned), move(turned, -7), hint(turned), reduced(turned), list(turned), move(turned, 1), list(turned),
      reduced(R(Sized())), type(copy.copy(R(Sized()))).__name__)

# iter(callable, sentinel) and the four that wrap iterators: __reduce__ is the call that made them, over the same iterators
stack = [0, 3, 2, 1]
popping = iter(stack.pop, 0)
print("iter(callable, sentinel):", [n for n in NAMES if n in vars(type(popping))], reduced(popping), next(popping), reduced(popping), operator.length_hint(popping, 7),
      list(popping), reduced(popping), attempt(lambda: hint(popping)), type(type(popping).__reduce__).__name__)
counted = enumerate("abc", 5)
print("enumerate:", [n for n in NAMES if n in vars(enumerate)], reduced(counted), next(counted), reduced(counted), reduced(enumerate("ab", 2 ** 70)), reduced(E("ab")),
      type(copy.copy(E("ab"))).__name__)
twin = copy.copy(counted)
print("enumerate, copied over the same iterator:", list(twin), list(counted), list(copy.deepcopy(enumerate("ab", 2 ** 70))) == [(2 ** 70, "a"), (2 ** 70 + 1, "b")])
zipped = zip([1, 2, 3], "abc", strict=False)
print("zip:", [n for n in NAMES if n in vars(zip)], reduced(zipped), reduced(zip([1], "ab", strict=True)), reduced(zip()), reduced(Z("ab")), next(zipped), list(copy.copy(zipped)),
      list(zipped), attempt(lambda: list(copy.copy(zip([1], "ab", strict=True)))), list(copy.deepcopy(zip([1], "ab", strict=False))))
loose = zip([1], "ab", strict=False)
print("zip, made strict:", move(loose, ["yes"]), reduced(loose), attempt(lambda: list(loose)), move(loose, 0), reduced(loose), attempt(lambda: move(loose, Unbool())),
      attempt(lambda: move(loose)), attempt(lambda: move(zip(), 1, 2)))  # type: ignore[call-arg]
mapped = map(pow, [1, 2, 3], [2, 2, 2], strict=False)
print("map:", [n for n in NAMES if n in vars(map)], reduced(mapped), reduced(map(pow, [1], [2, 3], strict=True)), reduced(M(abs, [1])), next(mapped), list(copy.copy(mapped)),
      list(mapped), attempt(lambda: list(copy.copy(map(pow, [1], [2, 3], strict=True)))), list(copy.deepcopy(map(abs, [-1, -2]))))
unchecked = map(pow, [1], [2, 3], strict=False)
print("map, made strict:", move(unchecked, 1), reduced(unchecked), attempt(lambda: list(unchecked)), move(unchecked, ""), reduced(unchecked),
      attempt(lambda: move(unchecked, Unbool())))
kept = filter(None, [0, 1, 2])
print("filter:", [n for n in NAMES if n in vars(filter)], reduced(kept), reduced(filter(abs, [0])), reduced(F(None, [1])), next(kept), list(copy.copy(kept)), list(kept),
      list(copy.deepcopy(filter(None, [0, 1, 2]))))

# by name: a method of the type, with its docstring, and the arguments and the receiver it takes
of_list = type(iter([1]))
of_tuple = type(iter(()))
print("the descriptors:", repr(of_list.__reduce__), repr(of_list.__length_hint__), of_list.__setstate__.__name__, of_list.__setstate__.__qualname__,  # type: ignore[attr-defined]
      of_list.__setstate__.__objclass__ is of_list, repr(zip.__reduce__), repr(reversed.__setstate__), repr(type(iter(range(1))).__setstate__))  # type: ignore[attr-defined]
print("their docstrings:", {kind.__name__: [vars(kind)[n].__doc__ for n in NAMES if n in vars(kind)] for kind in (of_list, type(iter(range(1))), type(iter({})), zip, enumerate)})
one = iter([1])
print("their arguments:", attempt(lambda: one.__length_hint__(1)), attempt(lambda: one.__reduce__(1)), attempt(lambda: move(one)), attempt(lambda: move(one, 1, 2)),  # type: ignore[attr-defined, call-arg]
      attempt(lambda: one.__setstate__(state=1)), attempt(lambda: of_list.__length_hint__(5)), attempt(lambda: of_list.__setstate__(iter(()), 0)),  # type: ignore[attr-defined]
      attempt(lambda: of_tuple.__reduce__(one)), attempt(lambda: of_list.__reduce__()), of_list.__length_hint__(one), of_list.__setstate__(one, 1), list(one),  # type: ignore[attr-defined, call-arg]
      attempt(lambda: zip().__reduce__(1)), attempt(lambda: zip.__reduce__(5)), attempt(lambda: reversed.__setstate__(5, 0)), attempt(lambda: enumerate.__reduce__()),  # type: ignore[attr-defined, call-arg]
      attempt(lambda: map.__setstate__(map(abs, []))), attempt(lambda: reversed.__length_hint__(reversed(Sized()), 1)))  # type: ignore[attr-defined, call-arg]
print("the two iterators of a str:", type(iter("")).__name__, type(iter("ascii")).__name__, type(iter("ż")).__name__, type(iter("ascii")) is type(iter("ż")),
      type(iter("ż")).__mro__ == (type(iter("ż")), object), "__next__" in vars(type(iter("ż"))), next(iter("ż")), list(iter("aż€😀")), type(iter(Text("ascii"))).__name__,
      type(iter(Text(""))).__name__, type(iter("ascii" + "ż"[:0])).__name__, type(iter("aż"[:1])).__name__, reduced(iter(Text("ab"))), type(reduced(iter(Text("ab")))[1][0]).__name__)  # type: ignore[index]
