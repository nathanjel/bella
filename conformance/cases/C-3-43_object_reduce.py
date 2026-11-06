# clause: C-3-43
# spec: section 3
# status: P1
# source: Objects/typeobject.c (object___reduce_ex___impl, reduce_newobj, object_getstate_default, _PyObject_GetNewArguments), Lib/copyreg.py
"""What object says of an instance to whoever would copy it: __reduce_ex__ from protocol 2 up, __getstate__ with its dict and its
slots, what a class's __getnewargs__, __getnewargs_ex__, __getstate__ and __reduce__ change, and what cannot be pickled."""
# ruff: noqa: ANN001, ANN002, ANN003, ANN201, ANN202, ANN204, B018, B023, E501, E731, PLR0133, SLF001
import copyreg


def failed(f):  # type: ignore[no-untyped-def]
    try:
        f()
    except Exception as exc:
        return type(exc).__name__
    return "no error"


def shown(result):  # type: ignore[no-untyped-def]
    """A reduce value, with what cannot be printed as itself named."""
    if isinstance(result, tuple):
        return tuple(shown(item) for item in result)  # type: ignore[no-untyped-call]
    if result is copyreg.__newobj__:  # type: ignore[attr-defined]
        return "__newobj__"
    if result is copyreg.__newobj_ex__:  # type: ignore[attr-defined]
        return "__newobj_ex__"
    if result is copyreg._reconstructor:  # type: ignore[attr-defined]
        return "_reconstructor"
    if isinstance(result, type):
        return result.__name__
    if isinstance(result, (int, str, bytes, float, list, dict, type(None))):
        return result
    return type(result).__name__


def reduced(instance, protocol):  # type: ignore[no-untyped-def]
    try:
        return shown(instance.__reduce_ex__(protocol))  # type: ignore[no-untyped-call]
    except Exception as exc:
        return type(exc).__name__


class Plain:
    pass


class Filled:
    def __init__(self):  # type: ignore[no-untyped-def]
        self.a = 1
        self.b = "two"


class Slotted:
    __slots__ = ("x", "y")

    def __init__(self):  # type: ignore[no-untyped-def]
        self.x = 1


class Both(Slotted):
    def __init__(self):  # type: ignore[no-untyped-def]
        super().__init__()  # type: ignore[no-untyped-call]
        self.z = 3


class Private:
    __slots__ = ("__hidden", "plain", "__dunder__")

    def __init__(self):  # type: ignore[no-untyped-def]
        self.__hidden = 1
        self.plain = 2
        self.__dunder__ = 3


class SlotDict:
    __slots__ = ("__dict__", "__weakref__", "s")

    def __init__(self):  # type: ignore[no-untyped-def]
        self.s = 1
        self.d = 2


class WithArgs:
    def __init__(self, a=0):  # type: ignore[no-untyped-def]
        self.a = a

    def __getnewargs__(self):  # type: ignore[no-untyped-def]
        return (self.a,)


class WithArgsEx:
    def __getnewargs_ex__(self):  # type: ignore[no-untyped-def]
        return ((1, 2), {"k": 3})


class WithEmptyKeywords:
    def __getnewargs_ex__(self):  # type: ignore[no-untyped-def]
        return ((1,), {})


class WithBothArgs:
    def __getnewargs_ex__(self):  # type: ignore[no-untyped-def]
        return ((1,), {})

    def __getnewargs__(self):  # type: ignore[no-untyped-def]
        return (9,)


class WithState:
    def __getstate__(self):  # type: ignore[no-untyped-def]
        return {"state": 1}


class NoState:
    def __getstate__(self):  # type: ignore[no-untyped-def]
        return None


class ReduceOverride:
    def __reduce__(self):  # type: ignore[no-untyped-def]
        return ("override", 1)


class ReduceExOverride:
    def __reduce_ex__(self, protocol):  # type: ignore[no-untyped-def]
        return ("override_ex", protocol)


class Dicter(dict):  # type: ignore[type-arg]
    def __init__(self):  # type: ignore[no-untyped-def]
        super().__init__(a=1)
        self.extra = 1


class Inty(int):
    pass


class Floaty(float):
    pass


class Tuply(tuple):  # type: ignore[type-arg]
    pass


class Bad1:
    def __getnewargs_ex__(self):  # type: ignore[no-untyped-def]
        return 1


class Bad2:
    def __getnewargs_ex__(self):  # type: ignore[no-untyped-def]
        return (1,)


class Bad3:
    def __getnewargs_ex__(self):  # type: ignore[no-untyped-def]
        return (1, {})


class Bad4:
    def __getnewargs_ex__(self):  # type: ignore[no-untyped-def]
        return ((), 1)


class Bad5:
    def __getnewargs__(self):  # type: ignore[no-untyped-def]
        return 1


class BadSlots:
    __slotnames__ = 1


class SlotNames:
    __slots__ = ("a",)
    __slotnames__ = ["a", "missing"]

    def __init__(self):  # type: ignore[no-untyped-def]
        self.a = 1


for make in (object, Plain, Filled, Slotted, Both, Private, SlotDict, WithArgs, WithArgsEx, WithEmptyKeywords, WithBothArgs, WithState, NoState, ReduceOverride, ReduceExOverride, Dicter, Tuply, BadSlots, SlotNames):
    instance = make()
    print(make.__name__)
    for protocol in (-1, 0, 1, 2, 3, 4, 5, 100):
        print(protocol, reduced(instance, protocol))  # type: ignore[no-untyped-call]
    print(failed(lambda: instance.__reduce_ex__()), failed(lambda: instance.__reduce_ex__("a")), failed(lambda: instance.__reduce_ex__(1.5)), failed(lambda: instance.__reduce_ex__(2**70)), failed(lambda: instance.__reduce_ex__(2, 3)), failed(lambda: instance.__getstate__(1)))  # type: ignore[arg-type,call-arg,no-untyped-call]
    print(shown(instance.__getstate__()) if make is not BadSlots else failed(lambda: instance.__getstate__()))  # type: ignore[no-untyped-call]
    print("__slotnames__" in vars(make), vars(make).get("__slotnames__"))
for value in (Bad1(), Bad2(), Bad3(), Bad4(), Bad5()):
    print(type(value).__name__, failed(lambda: value.__reduce_ex__(2)), failed(lambda: value.__getstate__()))  # type: ignore[no-untyped-call]

# ---- instances of built-in types: their state is in their args
for value in (1, True, 2**70, -5, "text", 1.5, (1, 2), (), b"bytes", [1, 2], {"a": 1}, Inty(5), Floaty(0.5), Tuply((1,))):  # type: ignore[assignment]
    print(type(value).__name__, shown(value.__reduce_ex__(2)), shown(value.__getstate__()))  # type: ignore[no-untyped-call]
for make in (lambda: lambda: 0, lambda: copyreg, lambda: (i for i in ()), lambda: property(), lambda: staticmethod(max), lambda: classmethod(max), lambda: super(Plain, Plain()), lambda: int):  # type: ignore[arg-type,assignment,var-annotated]
    value = make()  # type: ignore[assignment]
    print(type(value).__name__, failed(lambda: value.__reduce_ex__(2)), failed(lambda: value.__getstate__()))  # type: ignore[no-untyped-call]
print(object.__reduce_ex__, object.__getstate__, object.__reduce__, type(object.__reduce_ex__).__name__, type(object().__reduce_ex__).__name__, object.__reduce_ex__.__objclass__, object.__reduce_ex__.__name__, object.__getstate__.__qualname__)  # type: ignore[attr-defined]
print(failed(lambda: object.__reduce_ex__()), failed(lambda: object.__reduce_ex__(1)), object.__reduce_ex__(Plain(), 2)[1][0] is Plain, failed(lambda: object.__getstate__()), object.__getstate__(1), object.__getstate__(Filled()), failed(lambda: object.__reduce__()), failed(lambda: object().__reduce__(1)))  # type: ignore[call-arg,no-untyped-call]
print(copyreg._slotnames(Slotted), copyreg._slotnames(Both), copyreg._slotnames(Private), copyreg._slotnames(Plain), copyreg._slotnames(SlotDict), copyreg.dispatch_table[complex].__name__, sorted(copyreg.__all__))  # type: ignore[attr-defined]
print(copyreg.__newobj__(Plain).__class__ is Plain, copyreg.__newobj_ex__(WithArgs, (), {}).__class__ is WithArgs)  # type: ignore[attr-defined]
copyreg.pickle(Plain, lambda obj: (Plain, ()))
print(copyreg.dispatch_table[Plain](Plain())[0] is Plain, failed(lambda: copyreg.pickle(Plain, 1)), failed(lambda: copyreg.constructor(1)))  # type: ignore[arg-type,no-untyped-call]
print(shown(Plain().__reduce_ex__(2)))  # type: ignore[no-untyped-call]
