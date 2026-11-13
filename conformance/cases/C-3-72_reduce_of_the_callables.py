# clause: C-3-72
# spec: section 3 (the data model: what a type has of its own), section 6 (builtins)
# status: P1
# source: Objects/rangeobject.c (range_reduce), Objects/sliceobject.c (slice_reduce, ellipsis_reduce), Objects/object.c (NotImplemented_reduce),
#         Objects/methodobject.c (meth_reduce), Objects/classobject.c (method___reduce___impl), Objects/descrobject.c (descr_reduce,
#         wrapper_reduce), Python/symtable.c (_Py_IsPrivateName, _Py_Mangle)
"""How a range, a slice, the two named singletons and the callables say they are made again. `__reduce__` of a range or a
slice is its type and its three fields; of Ellipsis and NotImplemented, and of a built-in function of a module, its name;
of a built-in method, a bound method, a method-wrapper and a descriptor of a type, `getattr` with what it is bound to (or
the type it is of) and its name, a private name mangled as the class body would. So copy.copy of a bound method is a method
of the same object. The types that give none of their own (a function, a getset, None) are refused by object's."""
import collections
import copy
import functools
import math
import os
import sys
import types
from collections.abc import Callable


class K:
    def m(self) -> str:
        return "m"

    def __private(self) -> str:
        return "private"

    def reach(self) -> Callable[[], str]:
        return self.__private

    @classmethod
    def cm(cls) -> str:
        return "cm"

    @classmethod
    def __hidden(cls) -> str:
        return "hidden"

    @classmethod
    def reach_class(cls) -> Callable[[], str]:
        return cls.__hidden

    def __repr__(self) -> str:
        return "K()"


class _Leading:
    def __own(self) -> str:
        return "own"

    def reach(self) -> Callable[[], str]:
        return self.__own

    def __repr__(self) -> str:
        return "_Leading()"


class __:  # noqa: N801  # a class of underscores only: nothing to mangle with
    def __bare(self) -> str:
        return "bare"

    def reach(self) -> Callable[[], str]:
        return self.__bare

    def __repr__(self) -> str:
        return "__()"


class Slotted:
    __slots__ = ("x",)


class Named:
    """A callable with a name that is no str."""

    __name__ = 5

    def __call__(self, *args: object) -> str:
        return "called"


def attempt(thunk: Callable[[], object]) -> str:
    try:
        result = thunk()
    except Exception as exc:  # noqa: BLE001  # which exception, by class
        return type(exc).__name__
    return ascii(result)


def reduced(value: object) -> object:
    """__reduce__(): a name as it is, a call with the callable by its name."""
    made = value.__reduce__()
    if isinstance(made, str):
        return made
    return (getattr(made[0], "__name__", made[0]), *made[1:])


def again(value: object) -> object:
    """What the call __reduce__ gives makes."""
    made = value.__reduce__()
    assert isinstance(made, tuple)
    return made[0](*made[1])


def call_again(value: object, *args: object) -> object:
    """What the call __reduce__ gives makes, called."""
    made = again(value)
    assert callable(made)
    return made(*args)


def dotted() -> str:
    return "dotted"


k = K()
spread = range(1, 10, 2)
print("a range:", reduced(spread), reduced(range(0)), reduced(range(2 ** 70, -(2 ** 70), -3)), spread.__reduce_ex__(4) == spread.__reduce__(), again(spread) == spread,
      again(spread) is spread, type(vars(range)["__reduce__"]).__name__, vars(range)["__reduce__"].__doc__)
cut = slice(1, None, "x")
print("a slice:", reduced(cut), reduced(slice(2)), reduced(slice(k, [1], (2,))), cut.__reduce_ex__(2) == cut.__reduce__(), again(cut) == cut, again(cut) is cut,
      cut.__reduce__()[1][2] is cut.step, type(vars(slice)["__reduce__"]).__name__, vars(slice)["__reduce__"].__doc__)
print("the two singletons:", reduced(...), reduced(NotImplemented), (...).__reduce_ex__(4), NotImplemented.__reduce_ex__(0), type(vars(type(...))["__reduce__"]).__name__,
      "__reduce__" in vars(type(NotImplemented)), "__reduce__" in vars(type(None)), attempt(lambda: None.__reduce__()), attempt(lambda: type(...).__reduce__(None)))
items = [1]
queue = collections.deque([2])
print("a module's function:", reduced(len), reduced(math.sqrt), reduced(print), reduced(sys.exit), reduced(os.getcwd), reduced(functools.reduce), reduced(copy.copy.__call__) == ("getattr", (copy.copy, "__call__")),  # type: ignore[operator]
      len.__reduce_ex__(3), types.BuiltinFunctionType.__reduce__(repr), type(vars(types.BuiltinFunctionType)["__reduce__"]).__name__)
print("a built-in method:", reduced(items.append), reduced("ab".upper), reduced((5).bit_length), reduced(dict.fromkeys), reduced(str.maketrans), reduced(queue.append),
      reduced(None.__format__), reduced(k.__dir__), reduced(object.__new__), reduced(int.from_bytes), items.append.__reduce__()[1][0] is items, call_again(items.append, 3), items,
      call_again(dict.fromkeys, "a"), call_again("ab".upper), str.maketrans.__self__ is str, dict.fromkeys.__self__ is dict, object.__new__.__self__ is object, len.__self__ is sys.modules["builtins"])  # type: ignore[attr-defined]
bound = k.m
print("a bound method:", reduced(bound), reduced(k.reach()), reduced(K.cm), reduced(K.reach_class()), reduced(_Leading().reach()), reduced(__().reach()),
      bound.__reduce__()[1][0] is k, again(bound) == bound, again(bound) is bound, call_again(k.reach()), call_again(K.reach_class()), call_again(_Leading().reach()), call_again(__().reach()),
      bound.__reduce_ex__(4) == bound.__reduce__(), type(vars(type(bound))["__reduce__"]).__name__)
dotted.__name__ = "__a.b"
print("a bound method of any callable:", reduced(types.MethodType(len, [1, 2])), attempt(lambda: again(types.MethodType(len, [1, 2]))), reduced(types.MethodType(dotted, k)),
      attempt(lambda: reduced(types.MethodType(functools.partial(len), k))), reduced(types.MethodType(Named(), k)), reduced(types.MethodType(K.m, 5)),
      reduced(types.MethodType(items.append, k)), reduced(types.MethodType(K, 1)))
own_init = k.__init__  # type: ignore[misc]
print("a method-wrapper:", reduced((1).__add__), reduced(own_init), reduced(items.__len__), reduced(None.__eq__), reduced("a".__mod__), call_again((1).__add__, 2), call_again(items.__len__),
      again((1).__add__) == (1).__add__, type(vars(type(own_init))["__reduce__"]).__name__)
print("a descriptor:", reduced(list.append), reduced(int.__add__), reduced(slice.start), reduced(Slotted.x), reduced(collections.deque.append), reduced(object.__init__),  # type: ignore[attr-defined]
      again(list.append) is list.append, again(int.__add__) is int.__add__, again(slice.start) is slice.start,
      again(Slotted.x) is Slotted.x, sorted({type(vars(type(d))["__reduce__"]).__name__ for d in (list.append, int.__add__, slice.start)}))  # type: ignore[attr-defined]
print("none of their own:", [t.__name__ for t in (type(int.real), type(vars(dict)["fromkeys"]), type(dotted), type(None), type, int, type(sys), property) if "__reduce__" in vars(t)],
      attempt(lambda: int.real.__reduce__()), attempt(lambda: vars(dict)["fromkeys"].__reduce__()), attempt(lambda: dotted.__reduce__()), attempt(lambda: None.__reduce_ex__(1)),
      attempt(lambda: sys.__reduce__()))
grab = items.append
print("copied:", copy.copy(bound) == bound, copy.copy(bound) is bound, copy.copy(bound).__self__ is k, copy.deepcopy(bound).__self__ is k, copy.deepcopy(bound)(),  # type: ignore[attr-defined]
      copy.copy(list.append) is list.append, copy.copy(int.__add__) is int.__add__, copy.copy((1).__add__) == (1).__add__, copy.copy(k.reach())(), copy.copy(K.cm)(),
      attempt(lambda: copy.copy(types.MethodType(len, [1, 2]))), copy.copy(slice.start) is slice.start, copy.copy(grab) is grab, copy.copy(len) is len,
      copy.deepcopy(spread) is spread, copy.copy(cut) is cut, copy.copy(...) is ..., copy.copy(items.__len__)())
print("arguments:", [attempt(lambda v=v: v.__reduce__(1)) for v in (spread, cut, ..., NotImplemented, len, items.append, bound, (1).__add__, list.append, int.__add__, slice.start)],  # type: ignore[misc]
      attempt(lambda: len.__reduce__(x=1)), attempt(lambda: types.BuiltinFunctionType.__reduce__(5)), attempt(lambda: type(bound).__reduce__(len)), attempt(lambda: range.__reduce__(cut)),  # type: ignore[call-arg]
      attempt(lambda: type(list.append).__reduce__(int.__add__)), attempt(lambda: type((1).__add__).__reduce__(list.append)), attempt(lambda: range.__reduce__()),  # type: ignore[call-arg]
      type(len.__reduce__).__name__, repr(range.__reduce__), repr(type(bound).__reduce__), range.__reduce__.__qualname__)
