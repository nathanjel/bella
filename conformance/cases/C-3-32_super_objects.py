# clause: C-3-32
# spec: section 3 (the data model)
# status: P1
# source: TODO task 2 (super()); step 3b of the C++ leg starts with it
"""A super object looks a name up in the MRO of the object's type, after the class it names, and
binds what it finds with the object (None for a class) and the object's type, as
super_getattro does: cooperative calls follow the MRO, a property runs its getter, a
classmethod gets the type. Its own attributes (__thisclass__, __self__, __self_class__,
__class__) are not looked up there. super(T) is unbound until __get__ binds it. The checks:
super(type, obj) needs obj an instance or subtype of type, and a zero-argument super() needs
a first argument and the __class__ cell."""


class Shown:
    """A descriptor that prints what it is bound with."""

    def __get__(self, obj: object, owner: type | None = None) -> str:
        return "bound with " + type(obj).__name__ + " and " + (owner.__name__ if owner is not None else "None")


class Base:
    attr = "Base.attr"
    shown = Shown()

    def __init__(self) -> None:
        print("Base.__init__")

    def who(self) -> str:
        return "Base"

    @classmethod
    def make(cls) -> str:
        return "Base.make for " + cls.__name__

    @staticmethod
    def tool() -> str:
        return "Base.tool"

    @property
    def prop(self) -> str:
        return "Base.prop of " + type(self).__name__


class Left(Base):
    def __init__(self) -> None:
        print("Left.__init__")
        super().__init__()

    def who(self) -> str:
        return "Left>" + super().who()


class Right(Base):
    attr = "Right.attr"

    def __init__(self) -> None:
        print("Right.__init__")
        super().__init__()

    def who(self) -> str:
        return "Right>" + super().who()


class Bottom(Left, Right):
    def __init__(self) -> None:
        print("Bottom.__init__")
        super().__init__()

    def who(self) -> str:
        return "Bottom>" + super().who()

    @classmethod
    def make(cls) -> str:
        return "Bottom>" + super().make()

    def through(self) -> list[str]:
        s = super()
        return [s.attr, s.tool(), s.prop, s.shown, super(Left, self).attr, super(Right, self).attr]  # type: ignore[attr-defined]  # the stubs lack super's attributes


b = Bottom()
print("MRO:", [c.__name__ for c in Bottom.__mro__])
print(b.who())
print(Bottom.make(), super(Bottom, Bottom).make())
print(b.through())
print("from the class:", super(Left, Bottom).shown)

# the super object's own attributes
s = super(Left, b)
print(type(s).__name__, s.__class__.__name__, s.__thisclass__.__name__, s.__self__ is b, s.__self_class__.__name__)  # type: ignore[attr-defined]  # the stubs lack super's attributes
print(repr(s))
print(repr(super(Left, Bottom)), super(Left, Bottom).__self__ is Bottom, super(Left, Bottom).__self_class__.__name__)  # type: ignore[misc]  # the stubs lack super's attributes

# unbound, then bound by __get__
unbound = super(Left)
print(repr(unbound), unbound.__self__, unbound.__self_class__)  # type: ignore[attr-defined]  # the stubs lack super's attributes
print(unbound.__get__(b, Bottom).who(), unbound.__get__(None, Bottom) is unbound)  # type: ignore[attr-defined]  # the stubs lack super's attributes
print(s.__get__(Base(), Base) is s)  # type: ignore[attr-defined]  # the stubs lack super's attributes

# what it refuses
for thunk_name, args in (("super(1, b)", (1, b)), ("super(Left, 1)", (Left, 1)), ("super(Right, Left())", (Right, Left())),
                         ("super(Left, b, 3)", (Left, b, 3))):
    try:
        super(*args)
        print(thunk_name, "made")
    except TypeError:
        print(thunk_name, "TypeError")
try:
    super(Left, b).missing  # type: ignore[misc]  # the stubs lack super's attributes  # noqa: B018
except AttributeError:
    print("missing: AttributeError")
try:
    super(Left, b).attr = 1  # type: ignore[misc]  # a store through super, on purpose
except AttributeError:
    print("store: AttributeError")


class Odd(Base):
    @staticmethod
    def no_first() -> str:
        return super().who()  # type: ignore[misc, no-any-return]  # no first argument: the RuntimeError is the point


try:
    Odd.no_first()
except RuntimeError:
    print("no first argument: RuntimeError")
