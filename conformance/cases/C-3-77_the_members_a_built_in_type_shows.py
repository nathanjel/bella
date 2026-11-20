# clause: C-3-77
# spec: section 3 (the object model: what a built-in type keeps for itself)
# status: P1
# source: Modules/_functoolsmodule.c (partial_memberlist, partial_call, partial_new), Objects/genericaliasobject.c (ga_members),
#         Objects/unionobject.c (union_members), Modules/_struct.c (s_members), Modules/_io/textio.c and bufferedio.c (the
#         _finalizing member, Py_T_BOOL), Python/structmember.c (PyMember_SetOne), Objects/descrobject.c (member_get, member_set)
"""Some fields of a built-in type's struct the type shows, as members: partial's func, args and keywords, a generic
alias's __origin__, a stream's _finalizing. A member reads its field whatever name a class has it under; a read-only one
refuses a store and a delete by every way to it; and a class that derives from the type may have an attribute, a
property or a slot of the member's name, which a program then sees while the type's own work keeps its field."""
import functools
import io
import os
import struct
import types
from collections.abc import Callable


def outcome(act: Callable[[], object]) -> str:
    try:
        return repr(act())
    except (AttributeError, TypeError) as e:
        return type(e).__name__


def ways_to_change(obj: object, name: str, value: object) -> list[str]:
    """A store by the name, through object.__setattr__ and through the member; a delete by the name and through the member."""
    member = getattr(type(obj), name)
    return [outcome(lambda: setattr(obj, name, value)), outcome(lambda: object.__setattr__(obj, name, value)),
            outcome(lambda: member.__set__(obj, value)), outcome(lambda: delattr(obj, name)), outcome(lambda: member.__delete__(obj))]


def a_flag(stream: object, name: str) -> list[str]:
    """What a Py_T_BOOL member takes: read, two stores of what is no bool, a delete, a store of True, read again."""
    rows = [outcome(lambda: getattr(stream, name)), outcome(lambda: setattr(stream, name, 1)), outcome(lambda: setattr(stream, name, "yes")),
            outcome(lambda: delattr(stream, name)), outcome(lambda: setattr(stream, name, True)), outcome(lambda: getattr(stream, name))]
    setattr(stream, name, False)
    return rows


print("---- a read-only member, by every way to it")
p = functools.partial(abs, -4)
alias = list[int]
union = int | str
packer = struct.Struct("<i")
READ_ONLY: list[tuple[str, object, str, object]] = [
    ("partial.func", p, "func", len), ("partial.args", p, "args", (-77,)), ("partial.keywords", p, "keywords", {}),
    ("GenericAlias.__origin__", alias, "__origin__", tuple), ("GenericAlias.__args__", alias, "__args__", (str,)),
    ("GenericAlias.__unpacked__", alias, "__unpacked__", True), ("Union.__args__", union, "__args__", (float, bool)),
    ("Struct.size", packer, "size", 1), ("Struct.format", packer, "format", "<q"),
]
for label, obj, name, value in READ_ONLY:
    print(f"{label}: {type(getattr(type(obj), name)).__name__}, {ways_to_change(obj, name, value)}")
print("and nothing changed:", p(), alias, union, packer.size, packer.format, len(packer.pack(1)))

print("---- a member under a second name reads its own field")


class Aliased(functools.partial[int]):
    saved_args = functools.partial.args
    _p_phcount = functools.partial.func


aliased = Aliased(abs, -2)
print(aliased.saved_args, aliased._p_phcount is abs, aliased(), functools.partial.keywords.__get__(aliased))

print("---- a class attribute, a property and a slot of the member's name")


class Shadowed(functools.partial[int]):
    func = str  # type: ignore[assignment]
    args = (99,)


shadowed = Shadowed(abs, -3)
print("a class attribute:", shadowed.func is str, shadowed.args, shadowed(), functools.partial.args.__get__(shadowed), sorted(vars(shadowed)))
shadowed.args = "the instance's own"  # type: ignore[assignment]
print("then its own attribute:", shadowed.args, shadowed(), functools.partial.args.__get__(shadowed), sorted(vars(shadowed)))


class Reported(functools.partial[int]):
    @property
    def keywords(self) -> str:  # type: ignore[override]
        return "a property"


reported = Reported(int, "11", base=2)
print("a property:", reported.keywords, reported(), functools.partial.keywords.__get__(reported))


class Slotted(functools.partial[int]):
    __slots__ = ("func",)


slotted = Slotted(abs, -5)
print("a slot:", outcome(lambda: slotted.func), slotted(), functools.partial.func.__get__(slotted) is abs)
slotted.func = "mine"  # type: ignore[misc,assignment]
print("a slot, given a value:", slotted.func, slotted(), functools.partial.func.__get__(slotted) is abs)


class Origin(types.GenericAlias):
    @property
    def __origin__(self) -> type:
        return tuple


origin = Origin(list, int)
made: object = origin()  # type: ignore[operator]
print("a generic alias:", origin.__origin__ is tuple, repr(origin), type(made).__name__, types.GenericAlias.__origin__.__get__(origin) is list)

print("---- a stream's _finalizing is True or False, and is never deleted")
LOG: list[str] = []


class Watched(io.TextIOWrapper):
    def __setattr__(self, name: str, value: object) -> None:
        LOG.append(name)
        super().__setattr__(name, value)


watched = Watched(io.BytesIO())
print("making a stream asks no __setattr__:", LOG)
watched.close()
FLAG = "_finalizing"
STREAMS: list[tuple[str, io.IOBase]] = [("TextIOWrapper", io.TextIOWrapper(io.BytesIO())), ("BufferedWriter", io.BufferedWriter(io.BytesIO())),
                                       ("BufferedReader", io.BufferedReader(io.BytesIO())), ("FileIO", io.FileIO(os.devnull))]
for label, stream in STREAMS:
    print(f"{label}: {type(getattr(type(stream), FLAG)).__name__}, {a_flag(stream, FLAG)}")
    stream.close()

print("---- what a class statement leaves is not a type's")
ALIAS_ITERATOR: type = type(iter(list[int]))  # type: ignore[call-overload]
for label, kind in (("GenericAlias", types.GenericAlias), ("its iterator", ALIAS_ITERATOR), ("partial", functools.partial),
                    ("Struct", struct.Struct), ("TextIOWrapper", io.TextIOWrapper)):
    left = [name for name in ("__slots__", "__static_attributes__", "__firstlineno__", "__readonly__", "__boolean__") if name in vars(kind)]
    print(f"{label}: {left}")
print("the alias's iterator is made by iter() alone:", outcome(ALIAS_ITERATOR))
