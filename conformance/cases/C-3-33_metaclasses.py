# clause: C-3-33
# spec: section 3 (the data model)
# status: P1
# source: TODO task 2 (metaclasses); step 3b of the C++ leg (abc and enum need them)
"""A metaclass is a subclass of type, and a class is its instance. Making the class: the
metaclass's __prepare__, the body, its __new__ (through type.__new__, which runs __set_name__ and
__init_subclass__), its __init__; the metaclass is the most derived of the bases' (a conflict is a
TypeError), also for type(name, bases, ns). Then the metaclass serves the class as a class
serves its instances: its methods and properties bind to the class (a data descriptor of the
metaclass before the class's own attribute), its __call__ makes the instances, its __getattr__
and __setattr__ see the class's attributes, its special methods (__repr__, __len__, __iter__,
__contains__, __getitem__, __bool__) work on the class, and __instancecheck__ and
__subclasscheck__ decide isinstance and issubclass."""


class Named:
    def __set_name__(self, owner: type, name: str) -> None:
        print("set_name", owner.__name__, name)


class Meta(type):
    @classmethod
    def __prepare__(mcls, name: str, bases: tuple[type, ...], /, **kw: object) -> dict[str, object]:
        print("prepare", name, [b.__name__ for b in bases], kw)
        return {"from_prepare": 1}

    def __new__(mcls, name: str, bases: tuple[type, ...], ns: dict[str, object], **kw: object) -> Meta:
        print("new", mcls.__name__, name, [k for k in ns if k[:2] != "__"], kw)
        return super().__new__(mcls, name, bases, ns, **kw)

    def __init__(cls, name: str, bases: tuple[type, ...], ns: dict[str, object], **kw: object) -> None:
        print("init", cls.__name__, kw)
        super().__init__(name, bases, ns)

    def __call__(cls, *args: object) -> object:
        print("call", cls.__name__, args)
        return super().__call__(*args)

    def __repr__(cls) -> str:
        return "<Meta class " + cls.__name__ + ">"

    def __len__(cls) -> int:
        return 3

    def __iter__(cls) -> object:
        return iter(["a", "b", "c"])

    def __contains__(cls, item: object) -> bool:
        return item == "b"

    def __getitem__(cls, key: str) -> str:
        return "item " + key

    def __getattr__(cls, name: str) -> str:
        return "missing " + name

    def describe(cls) -> str:
        return "described " + cls.__name__

    @property
    def tag(cls) -> str:
        return "Meta.tag of " + cls.__name__

    shared = "Meta.shared"


class Base(metaclass=Meta):
    marker = Named()
    shared = "Base.shared"

    def __init_subclass__(cls, **kw: object) -> None:
        print("init_subclass", cls.__name__, kw)

    def __init__(self, value: object) -> None:
        self.value = value


class Child(Base, flavour="child"):
    tag = "Child.tag"                          # Meta.tag is a data descriptor: it wins


print(type(Base).__name__, type(Child) is Meta, isinstance(Child, Meta), Child.__class__.__name__)
print(repr(Child), str(Child), Child.describe(), Child.tag, Child.shared, Child.from_prepare)
print(Child.nonexistent, len(Child), list(Child), "b" in Child, "z" in Child, Child["k"], bool(Child))  # type: ignore[call-overload]  # the metaclass's __iter__, which the checker does not apply
c = Child(5)
print(type(c).__name__, c.value)
print(type("Made", (Base,), {"x": 1}).__name__)


class SubMeta(Meta):
    pass


class Third(metaclass=SubMeta):
    pass


class Mixed(Base, Third):                      # the most derived metaclass wins
    pass


print(type(Mixed).__name__)


class Other(type):
    pass


class Unrelated(metaclass=Other):
    pass


try:
    class Conflict(Base, Unrelated):  # type: ignore[metaclass]  # the conflict is the point
        pass
except TypeError:
    print("metaclass conflict: TypeError")


class Guarded(type):
    def __setattr__(cls, name: str, value: object) -> None:
        print("setattr on", cls.__name__, name)
        super().__setattr__(name, value)

    def __instancecheck__(cls, obj: object) -> bool:
        return obj == "anything"

    def __subclasscheck__(cls, sub: type) -> bool:
        return sub is int


class Checked(metaclass=Guarded):
    pass


Checked.x = 1                                 # set through the metaclass's __setattr__
print(Checked.x,  # type: ignore[attr-defined]  # the checker does not see the store above
      isinstance("anything", Checked), isinstance(Checked(), Checked), issubclass(int, Checked), issubclass(str, Checked))
print(type.__new__(Other, "Direct", (), {}).__name__, type(Other("ByCall", (), {})).__name__)
