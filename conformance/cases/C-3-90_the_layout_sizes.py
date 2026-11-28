# clause: C-3-90
# spec: section 3
# status: P1
# source: the author's decision of 2026-11-28 (Question 67): type.__basicsize__ and __itemsize__ as CPython's; RL-592
"""A type's __basicsize__ and __itemsize__ are CPython's numbers: a type written in C has its struct's, and a class its
base's, a pointer more for each slot it declares, and its base's item size (type_new); and the default __getstate__ of
an object of a class over a C type with fields gives the state where the slot names account for the struct, and refuses
it where they do not (object_getstate_default)."""
import collections
import functools
import io
import itertools
import weakref


class Plain:
    pass


class Slotted:
    __slots__ = ("a", "b")


class SlotsDict:
    __slots__ = ("a", "__dict__")


class SlotsWeak:
    __slots__ = ("a", "__weakref__")


class EmptySlots:
    __slots__ = ()


class MoreSlots(Slotted):
    __slots__ = ("c",)


class NoSlots(Slotted):
    pass


class IntSub(int):
    pass


class IntNoSlots(int):
    __slots__ = ()


class TupleSub(tuple[int, ...]):
    pass


class BytesSub(bytes):
    pass


class StrSub(str):
    pass


class ExcSub(Exception):
    pass


class ExcSlots(Exception):
    __slots__ = ("x",)


class DictSub(dict[str, int]):
    pass


class ListSub(list[int]):
    pass


class PropertySub(property):
    pass


TYPES: list[type] = [object, int, bool, float, complex, str, bytes, bytearray, tuple, list, dict, set, frozenset, type,
                     BaseException, Exception, KeyError, OSError, property, staticmethod, classmethod, range, slice,
                     enumerate, zip, functools.partial, collections.deque, collections.OrderedDict, itertools.chain,
                     io.BytesIO, io.StringIO, weakref.ref, Plain, Slotted, SlotsDict, SlotsWeak, EmptySlots, MoreSlots,
                     NoSlots, IntSub, IntNoSlots, TupleSub, BytesSub, StrSub, ExcSub, ExcSlots, DictSub, ListSub,
                     PropertySub]
for t in TYPES:
    print(t.__qualname__, t.__basicsize__, t.__itemsize__)


class Accounted(property):                       # the slot names cover property's fields: the state is the dict
    __slotnames__ = ["a", "b", "c", "d", "e", "f"]


class Short(property):                           # they do not: refused
    __slotnames__ = ["a"]


for cls in (Accounted, Short, PropertySub):      # reduce_newobj asks for the state as required, where the sizes are compared
    try:
        print(cls.__name__, cls().__reduce_ex__(2)[2])
    except TypeError as error:
        print(cls.__name__, type(error).__name__)
