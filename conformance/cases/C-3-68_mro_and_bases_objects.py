# clause: C-3-68
# spec: section 3
# status: P1
# source: Gate 1c, noted with C-3-65: C.__bases__ and C.__mro__ were a new tuple at each read
"""A class's __mro__ and __bases__ are objects, one each until they are replaced: every read gives
the same one, through the class or through type's descriptor, for a program's class and for a
built-in type. __bases__ is the very tuple the metaclass handed to type.__new__, or the one
assigned to the class later; a class made with no bases has an (object,) of its own. Assigning a
class the bases it has makes it and every subclass a new MRO tuple, equal to the old one, and
leaves its bases' MRO as it was."""

saved: dict[str, tuple[type, ...]] = {}


class Meta(type):
    def __new__(mcls, name: str, bases: tuple[type, ...], ns: dict[str, object]) -> "Meta":  # noqa: UP037  # the class being defined
        saved[name] = bases
        return super().__new__(mcls, name, bases, ns)


class A:
    pass


class B(A, metaclass=Meta):
    pass


class C(B):
    pass


class E(metaclass=Meta):
    pass


print("one object:", A.__mro__ is A.__mro__, A.__bases__ is A.__bases__, C.__mro__ is C.__mro__)
print("descriptor:", type.__dict__["__mro__"].__get__(B) is B.__mro__, type.__dict__["__bases__"].__get__(B) is B.__bases__)
print("built-in:", object.__mro__ is object.__mro__, int.__bases__ is int.__bases__, bool.__mro__ is bool.__mro__)
print("the tuple given:", B.__bases__ is saved["B"], "none given:", E.__bases__ is saved["E"], E.__bases__, saved["E"])
print("two classes with no bases:", A.__bases__ == E.__bases__, A.__bases__ is E.__bases__)
before = (A.__mro__, B.__mro__, C.__mro__, B.__bases__)
assigned = (A,)
B.__bases__ = assigned
print("assigned:", B.__bases__ is assigned, B.__bases__ is before[3])
print("mro again:", [(now is old, now == old) for now, old in zip((A.__mro__, B.__mro__, C.__mro__), before[:3], strict=True)])
print("then one object again:", B.__mro__ is B.__mro__, C.__mro__ is C.__mro__)
