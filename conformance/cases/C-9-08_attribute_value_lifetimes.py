# clause: C-9-08
# spec: section 9
# status: P1
# source: Gate 0 task 3, lifetimes in the reference model (review log RL-20, RL-49)
"""When an object's attribute values die, and in what order (measured on CPython 3.15.2).

A rebound attribute's old value dies at the rebinding, a deleted one at the `del`. When the
object dies, its __slots__ go first (the most-derived class's, then its bases', each sorted
by name, as CPython stores them when it makes the class), then its instance attributes in the order of the class's shared keys: the
sorted names its methods assign (__static_attributes__), then each name in the order any
instance first stored or tried to delete it, which is not the dying instance's own assignment
order. A dict made by
vars() outlives the object while referenced and releases in the same key order; a dict installed
by assigning __dict__ releases in insertion order; a shared dict dies with its last owner.
"""
log: list[str] = []


class Tag:
    def __init__(self, name: str) -> None:
        self.name = name

    def __del__(self) -> None:
        log.append(self.name)


def show(title: str) -> None:
    print(f"{title}: {log}")
    log.clear()


class Plain:
    # declarations only: no class attribute, and no __static_attributes__ (no method stores them)
    x: Tag
    y: Tag
    z: Tag
    w: Tag
    p: Tag
    q: Tag


first = Plain()
first.x = Tag("x1")
first.y = Tag("y1")
del first
show("first instance x, y")
later = Plain()
later.y = Tag("y2")
later.z = Tag("z2")
later.x = Tag("x2")
del later
show("key order x, y, z, whatever the instance's own order")
third = Plain()
third.w = Tag("w3")
third.x = Tag("x3")
del third
show("a new key joins the end")


class Init:
    a: Tag
    b: Tag

    def __init__(self) -> None:
        self.b = Tag("b")
        self.a = Tag("a")


init = Init()
del init
show("__init__ stores b, a: static attributes sorted")

o = Plain()
o.x = Tag("old")
o.x = Tag("new")
show("rebinding")
del o.x
show("del")
o.y = Tag("y")
d = vars(o)
del o
show("vars() kept, owner dies")
del d
show("then the dict")

o2 = Plain()
o2.y = Tag("y")
o2.x = Tag("x")
o2.__dict__ = {"q": Tag("q"), "p": Tag("p")}
show("__dict__ replaced: the old dict's values")
del o2
show("then the object: insertion order")

a1 = Plain()
a2 = Plain()
a1.x = Tag("shared")
a2.__dict__ = a1.__dict__
del a1
show("shared dict, first owner")
del a2
show("last owner")


class Slotted:
    __slots__ = ("p", "q")
    p: Tag
    q: Tag


class Derived(Slotted):
    __slots__ = ("r", "__dict__")
    r: Tag
    x: Tag


s = Derived()
s.x = Tag("x")
s.q = Tag("q")
s.r = Tag("r")
s.p = Tag("p")
del s
show("derived slots, base slots, then the dict")


class Unsorted:
    __slots__ = ("zeta", "alpha", "mid")
    zeta: Tag
    alpha: Tag
    mid: Tag


u = Unsorted()
u.zeta = Tag("zeta")
u.alpha = Tag("alpha")
u.mid = Tag("mid")
del u
show("slots sorted by name, not declared order")


class Probe:
    x: Tag
    y: Tag


probe = Probe()
try:
    del probe.y
except AttributeError:
    print("del of a missing attribute: AttributeError")
second = Probe()
second.x = Tag("x")
second.y = Tag("y")
del probe, second
show("a failed del puts y in the keys first")


class Holder:
    attr: Tag | None = None


Holder.attr = Tag("c1")
Holder.attr = Tag("c2")
show("class attribute replaced")
