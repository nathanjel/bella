# clause: C-3-78
# spec: section 3 (the object model: __slots__)
# status: P1
# source: Objects/typeobject.c (type_new_descriptors, type_new_slots, subtype_dealloc, clear_slots), Objects/descrobject.c
#         (member_get, member_set, descr_check, descr_setcheck), Python/structmember.c (PyMember_GetOne, PyMember_SetOne)
"""A class that declares a slot one of its bases has declares a second one: each declaration is a member of its own
class with a cell of its own in the object. The name reads the cell of whichever member the lookup finds, the nearest
class's while that class still has it; the base's member reads the base's cell, by itself, through super() and under
any name another class has it. A member of a class that is no base applies to none of the class's objects. An object
lets go of the most derived class's cells first."""
from collections import deque
from collections.abc import Callable
from types import MemberDescriptorType


def outcome(act: Callable[[], object]) -> str:
    try:
        return repr(act())
    except AttributeError:
        return "AttributeError"
    except TypeError:
        return "TypeError"


def member(cls: type, name: str) -> MemberDescriptorType:
    """The member a class itself has for one of its slots."""
    found = vars(cls)[name]
    assert isinstance(found, MemberDescriptorType)
    return found


class Noted:
    """A value that says when it goes."""

    def __init__(self, label: str) -> None:
        self.label = label

    def __repr__(self) -> str:
        return self.label

    def __del__(self) -> None:
        print("  gone:", self.label)


class D:
    __slots__ = ("x",)
    x: object


class F(D):
    __slots__ = ("x",)
    x: object


NAME = "x"
D_X, F_X = member(D, "x"), member(F, "x")
print("---- two members, two cells")
o = F()
o.x = "F's"
print("by the name:", o.x, "| the base's member:", outcome(lambda: D_X.__get__(o)), "| the class's own:", F_X.__get__(o))
D_X.__set__(o, "D's")
print("after a store through the base's member:", o.x, D_X.__get__(o), F_X.__get__(o))
print("the members:", D_X is F_X, repr(D_X), repr(F_X), D_X.__objclass__.__name__, F_X.__objclass__.__name__)
print("through super():", super(F, o).x, "| getattr:", getattr(o, NAME), "| object.__getattribute__:", object.__getattribute__(o, NAME))
del o.x
print("the name deleted:", outcome(lambda: o.x), "|", D_X.__get__(o), "| deleted again:", outcome(lambda: delattr(o, NAME)))
D_X.__delete__(o)
print("the base's deleted:", outcome(lambda: D_X.__get__(o)), "| deleted again:", outcome(lambda: D_X.__delete__(o)))
o.x = "back"
print("and stored again:", o.x, outcome(lambda: D_X.__get__(o)))

print("---- an object of the base has the one cell")
d = D()
d.x = "the base's only"
print(d.x, D_X.__get__(d), outcome(lambda: F_X.__get__(d)), outcome(lambda: F_X.__set__(d, 1)))

print("---- three declarations, and a class between that declares none")


class Between(F):
    __slots__ = ()


class G(Between):
    __slots__ = ("x", "y")
    x: object
    y: object


g = G()
for cls, value in ((D, "first"), (F, "second"), (G, "third")):
    member(cls, "x").__set__(g, value)
g.y = "y"
print(g.x, [member(cls, "x").__get__(g) for cls in (D, F, G)], g.y, super(G, g).x, super(Between, g).x, super(F, g).x)
print("an object of the class between:", outcome(lambda: member(G, "x").__get__(Between())))
f = F()
D_X.__set__(f, 1)
F_X.__set__(f, 2)
print("each object its own:", f.x, D_X.__get__(f), g.x, D_X.__get__(g))

print("---- the name reads the member the lookup finds")


class Top(D):
    __slots__ = ("x",)
    x: object


top = Top()
top.x = "Top's"
D_X.__set__(top, "D's")
kept = member(Top, "x")
readings = []
for turn in range(4):                                # one place in the program, before and after the class changes
    if turn == 2:
        type.__delattr__(Top, NAME)
    readings.append(top.x)
print(readings, "| the member taken away still reads its cell:", kept.__get__(top))
top.x = "stored by the name"
print("a store by the name goes where the lookup goes:", D_X.__get__(top), kept.__get__(top))
type.__setattr__(Top, NAME, kept)
print("the member put back:", top.x, D_X.__get__(top))


class Renamed(F):
    __slots__ = ()
    x = D_X
    other = F_X


r = Renamed()
r.x = "through D's member"
r.other = "through F's member"
print("a class that has the base's member under the name:", r.x, r.other, D_X.__get__(r), F_X.__get__(r))


def read(obj: F) -> object:
    return obj.x


plain = F()
plain.x = "F's own"
D_X.__set__(plain, "D's own")
print("one place, two classes:", [read(obj) for obj in (plain, r, plain, r)])

print("---- a member of a class that is no base applies to none of the class's objects")


class Elsewhere:
    __slots__ = ("x",)
    x: object


class Borrowed(D):
    __slots__ = ()
    x = member(Elsewhere, "x")


b = Borrowed()
print(outcome(lambda: b.x), outcome(lambda: setattr(b, NAME, 1)), outcome(lambda: delattr(b, NAME)), outcome(lambda: D_X.__get__(b)))
D_X.__set__(b, "D's")
print(outcome(lambda: b.x), D_X.__get__(b), outcome(lambda: object.__setattr__(b, NAME, 1)), outcome(lambda: object.__delattr__(b, NAME)))

print("---- over a built-in type, whose own field of the name is a third")


class Line(deque[int]):
    __slots__ = ("_a_items",)
    _a_items: object


class Queue(Line):
    __slots__ = ("_a_items",)
    _a_items: object


q = Queue([1, 2], 3)
member(Line, "_a_items").__set__(q, "Line's")
member(Queue, "_a_items").__set__(q, "Queue's")
q.append(3)
q.append(4)
print(q._a_items, member(Line, "_a_items").__get__(q), list(q), q.maxlen)

print("---- a private name is another name in each class")


class P:
    __slots__ = ("__p",)
    __p: str

    def __init__(self) -> None:
        self.__p = "P's"

    def p(self) -> str:
        return self.__p


class Q(P):
    __slots__ = ("__p",)
    __p: str

    def __init__(self) -> None:
        super().__init__()
        self.__p = "Q's"

    def q(self) -> str:
        return self.__p


pq = Q()
print(pq.p(), pq.q(), sorted(n for n in dir(pq) if n.endswith("__p")))

print("---- what goes first")


class Low:
    __slots__ = ("a", "x", "z")
    a: object
    x: object
    z: object


class High(Low):
    __slots__ = ("m", "x")
    m: object
    x: object


def fill() -> None:
    h = High()
    for cls, name in ((Low, "a"), (Low, "x"), (Low, "z"), (High, "m"), (High, "x")):
        member(cls, name).__set__(h, Noted(cls.__name__ + "." + name))
    print("  filled:", h.x, member(Low, "x").__get__(h))


fill()
print("---- a store over a value lets go of that cell's alone")
high = High()
high.x = Noted("High.x, first")
member(Low, "x").__set__(high, Noted("Low.x, kept"))
high.x = Noted("High.x, second")
print("  then:", high.x, member(Low, "x").__get__(high))
del high.x
print("  deleted by the name")
del high
print("---- the end")
