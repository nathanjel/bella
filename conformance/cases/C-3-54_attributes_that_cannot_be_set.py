# clause: C-3-54
# spec: section 3
# status: P1
# source: Objects/object.c (_PyObject_GenericSetAttrWithDict, _PyObject_SetAttributeErrorContext), Objects/descrobject.c (getset_set, member_set), Python/structmember.c (PyMember_SetOne), Objects/funcobject.c, Objects/classobject.c, Objects/typeobject.c (type_setattro)
"""Assigning to an attribute that cannot be assigned, and deleting one that cannot be deleted. What is raised, and what the
AttributeError carries: `name` and `obj` are set only where the object has no such attribute and no place to put one; where a
descriptor of the type refuses (a getset without a setter, a read-only member, a method of a type without a __dict__), the
error names nothing and holds no object. What each kind of object lets a program set, and what it refuses whatever the value."""
# ruff: noqa: E501
import functools
import io
import itertools
import operator
import types
from collections.abc import Callable, Iterator


class Slotted:
    __slots__ = ("unset", "x")


class SlottedWithNames:
    """Its instances have no __dict__, and its own names are not theirs to set."""

    __slots__ = ("never_set",)
    shared = 1

    def meth(self) -> None:
        pass


class Guarded:
    """Slotted, with a __setattr__ and a __delattr__ of its own, which hand on to object's."""

    __slots__ = ("x",)
    shared = 1

    def __setattr__(self, name: str, value: object) -> None:
        object.__setattr__(self, name, value)

    def __delattr__(self, name: str) -> None:
        super().__delattr__(name)


class WithProperty:
    @property
    def ro(self) -> int:
        return 1

    def meth(self) -> None:
        pass


class Plain:
    def meth(self) -> None:
        pass


def gen() -> Iterator[int]:
    yield 1


def f(a: int, b: int = 1) -> int:
    return a


def outcome(act: Callable[[], None], target: object) -> str:
    try:
        act()
    except AttributeError as e:
        carried = "none" if e.name is None and e.obj is None else "name and obj" if e.obj is target else "name only" if e.obj is None else "another object"
        return "AttributeError (" + carried + ")" + ("" if e.name is None else " " + str(e.name))
    except Exception as e:
        return type(e).__name__
    return "ok"


def show(label: str, target: object, name: str, value: object = None) -> None:
    print(label + ":", "set", outcome(lambda: setattr(target, name, value), target) + ";", "del", outcome(lambda: delattr(target, name), target))


def main() -> None:
    slotted = Slotted()
    plain = Plain()
    bound = plain.meth
    g = gen()
    cell = (lambda: slotted).__closure__[0]  # type: ignore[index]

    # numbers, text and containers: no __dict__, so a method is read-only and a new name has nowhere to go
    show("int.real", 1, "real", 2)
    show("int.new", 1, "new", 2)
    show("bool.real", True, "real", 1)
    show("float.imag", 1.5, "imag", 2)
    show("complex.real", 1j, "real", 2)
    show("str.upper", "s", "upper", 2)
    show("str.new", "s", "new", 2)
    show("bytes.new", b"s", "new", 2)
    show("tuple.count", (), "count", 2)
    show("list.append", [], "append", 2)
    show("list.new", [], "new", 2)
    show("dict.keys", {}, "keys", 2)
    show("frozenset.new", frozenset(), "new", 1)
    show("range.start", range(3), "start", 1)
    show("range.new", range(3), "new", 1)
    show("slice.start", slice(1), "start", 1)
    show("object().x", object(), "x", 1)
    show("None.x", None, "x", 1)
    show("NotImplemented.x", NotImplemented, "x", 1)
    show("Ellipsis.x", ..., "x", 1)
    show("int.__doc__ of an instance", 1, "__doc__", "d")

    # functions and methods
    show("bound.__func__", bound, "__func__", f)
    show("bound.__self__", bound, "__self__", 1)
    show("bound.new", bound, "new", 1)
    show("bound.__doc__", bound, "__doc__", "x")
    show("function.__closure__", f, "__closure__", None)
    show("function.__globals__", f, "__globals__", {})
    show("function.__builtins__", f, "__builtins__", {})
    show("function.__name__, not a str", f, "__name__", 1)
    show("function.__code__, not code", f, "__code__", 1)
    show("function.__defaults__, not a tuple", f, "__defaults__", 1)
    show("function.__dict__, not a dict", f, "__dict__", 1)
    show("function.__qualname__, not a str", f, "__qualname__", 1)
    show("function.__kwdefaults__, not a dict", f, "__kwdefaults__", 1)
    show("function.__wrapped__", f, "__wrapped__", f)
    show("function.new", f, "new", 1)
    show("len.__name__", len, "__name__", "x")
    show("len.__self__", len, "__self__", 1)
    show("len.new", len, "new", 1)
    show("str.upper.__name__", str.upper, "__name__", "x")
    show("code.co_name", f.__code__, "co_name", "x")
    show("cell.new", cell, "new", 5)
    show("generator.gi_running", g, "gi_running", 1)
    show("generator.gi_code", g, "gi_code", 1)
    show("generator.new", g, "new", 1)

    # classes and their instances
    show("slot, unset", slotted, "unset", 1)
    show("slot, missing", slotted, "missing", 1)
    with_names = SlottedWithNames()
    print("slot, never set: del", outcome(lambda: delattr(with_names, "never_set"), with_names) + ";", "by its member:", outcome(lambda: SlottedWithNames.never_set.__delete__(with_names), with_names))  # type: ignore[attr-defined]
    show("a class attribute of a slotted class", with_names, "shared", 2)
    show("a method of a slotted class", with_names, "meth", 2)
    show("__doc__ of a slotted class's instance", with_names, "__doc__", "d")
    show("__module__ of a slotted class's instance", with_names, "__module__", "m")
    print("by object's own methods:", outcome(lambda: object.__setattr__(with_names, "shared", 2), with_names), outcome(lambda: object.__delattr__(with_names, "meth"), with_names),
          outcome(lambda: object.__setattr__(with_names, "new", 2), with_names), outcome(lambda: object.__delattr__(with_names, "new"), with_names))
    guarded = Guarded()
    show("a class attribute, its class has a __setattr__", guarded, "shared", 2)
    show("a new name, its class has a __setattr__", guarded, "new", 2)
    show("a slot, its class has a __setattr__", guarded, "x", 2)
    show("property", WithProperty(), "ro", 1)
    show("a method of an instance", plain, "meth", 1)
    show("int.x", int, "x", 1)
    show("int.__name__", int, "__name__", "x")
    show("int.real of the type", int, "real", 1)
    show("int.__doc__", int, "__doc__", "d")
    show("class.__mro__", Plain, "__mro__", ())
    show("class.__dict__", Plain, "__dict__", {})
    show("class.__base__", Plain, "__base__", object)
    show("class.__qualname__, not a str", Plain, "__qualname__", 1)
    show("class.__abstractmethods__", Plain, "__abstractmethods__", ())
    show("class.__module__", Plain, "__module__", "m")
    show("class.__doc__", Plain, "__doc__", "d")
    show("instance.__dict__, not a dict", Plain(), "__dict__", 1)
    show("module.__dict__", types, "__dict__", {})
    show("mappingproxy.new", Plain.__dict__, "new", 1)
    show("Slotted.x.__name__", Slotted.x, "__name__", "y")  # type: ignore[attr-defined]
    show("super.__thisclass__", super(Plain, plain), "__thisclass__", int)
    show("SimpleNamespace.x", types.SimpleNamespace(), "x", 1)
    show("union.__doc__", int | str, "__doc__", "d")
    show("union.__module__", int | str, "__module__", "m")
    show("union.__or__", int | str, "__or__", 1)
    show("alias.__doc__", list[int], "__doc__", "d")
    show("alias.__module__", list[int], "__module__", "m")
    show("alias.__mro_entries__", list[int], "__mro_entries__", 1)

    # the library's C types (property, staticmethod and classmethod have a case of their own, C-3-55)
    show("partial.func", functools.partial(f), "func", f)
    show("partial.args", functools.partial(f), "args", ())
    show("itemgetter.new", operator.itemgetter(1), "new", 1)
    show("count.new", itertools.count(), "new", 1)
    show("BytesIO.closed", io.BytesIO(), "closed", True)
    show("StringIO.line_buffering", io.StringIO(), "line_buffering", True)
    show("exception.args", ValueError(1), "args", 5)
    show("exception.__traceback__", ValueError(1), "__traceback__", 5)
    show("exception.__cause__", ValueError(1), "__cause__", 5)
    show("exception.__context__", ValueError(1), "__context__", 5)


    # a function's own __dict__ can be given, any dict, and not taken away; its __doc__ deleted reads None
    def h() -> None:
        """doc"""

    h.x = 1  # type: ignore[attr-defined]
    mine = {"y": 2}
    h.__dict__ = mine
    print("a function's dict:", h.__dict__ is mine, h.y, hasattr(h, "x"), vars(h) is mine)  # type: ignore[attr-defined]
    del h.y  # type: ignore[attr-defined]
    del h.__doc__
    print("after deleting:", mine, h.__doc__, outcome(lambda: delattr(h, "y"), h), outcome(lambda: delattr(h, "__dict__"), h), h.__dict__ is mine)


if __name__ == "__main__":
    main()
