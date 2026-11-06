# clause: C-3-42
# spec: section 3
# status: P1
# source: Objects/descrobject.c, Objects/methodobject.c, Objects/typeobject.c (tp_new_wrapper)
"""What the methods of a type written in C are, whichever language the runtime writes the type in: a slot wrapper, a method
descriptor, a class method descriptor, a function bound to the type. What each says of itself, what binding makes of it, what it
checks of its receiver, and what object.__new__ says of the type. The table of names is what CPython and the runtime both have."""
# ruff: noqa: ANN001, ANN002, ANN003, ANN201, ANN202, ANN204, B018, B023, B911, E501, E731, PLR0133, SLF001
import _collections  # type: ignore[import-not-found]
import _thread
import collections
import functools
import itertools
import operator
import os
import types
import weakref


def failed(f):  # type: ignore[no-untyped-def]
    try:
        f()
    except Exception as exc:
        return type(exc).__name__
    return "no error"


def addressless(text):  # type: ignore[no-untyped-def]
    head, sep, _rest = text.partition(" at 0x")
    return head + (">" if sep else "")


def compare(a, b):  # type: ignore[no-untyped-def]
    return a < b


class Referent:
    pass


class Sequence:
    def __len__(self):  # type: ignore[no-untyped-def]
        return 0

    def __getitem__(self, index):  # type: ignore[no-untyped-def]
        raise IndexError


referent = Referent()
key_wrapper = type(functools.cmp_to_key(compare))
METHODS = {
    "itertools.accumulate": ["__new__", "__iter__", "__next__"],
    "itertools.batched": ["__new__", "__iter__", "__next__"],
    "itertools.chain": ["__new__", "__iter__", "__next__", "from_iterable", "__class_getitem__"],
    "itertools.combinations": ["__new__", "__iter__", "__next__"],
    "itertools.combinations_with_replacement": ["__new__", "__iter__", "__next__"],
    "itertools.compress": ["__new__", "__iter__", "__next__"],
    "itertools.count": ["__new__", "__repr__", "__iter__", "__next__"],
    "itertools.cycle": ["__new__", "__iter__", "__next__"],
    "itertools.dropwhile": ["__new__", "__iter__", "__next__"],
    "itertools.filterfalse": ["__new__", "__iter__", "__next__"],
    "itertools.groupby": ["__new__", "__iter__", "__next__"],
    "itertools.islice": ["__new__", "__iter__", "__next__"],
    "itertools.pairwise": ["__new__", "__iter__", "__next__"],
    "itertools.permutations": ["__new__", "__iter__", "__next__"],
    "itertools.product": ["__new__", "__iter__", "__next__"],
    "itertools.repeat": ["__new__", "__repr__", "__iter__", "__next__", "__length_hint__"],
    "itertools.starmap": ["__new__", "__iter__", "__next__"],
    "itertools.takewhile": ["__new__", "__iter__", "__next__"],
    "itertools.zip_longest": ["__new__", "__iter__", "__next__"],
    "collections.deque": ["__new__", "__repr__", "__lt__", "__le__", "__eq__", "__ne__", "__gt__", "__ge__", "__iter__", "__init__", "__len__", "__add__", "__mul__", "__rmul__", "__getitem__", "__setitem__", "__delitem__", "__contains__", "__iadd__", "__imul__", "append", "appendleft", "clear", "__copy__", "copy", "count", "extend", "extendleft", "index", "insert", "pop", "popleft", "__reduce__", "remove", "__reversed__", "reverse", "rotate", "__sizeof__", "__class_getitem__"],
    "collections.defaultdict": ["__repr__", "__init__", "__or__", "__ror__", "__missing__", "copy", "__copy__", "__reduce__", "__class_getitem__"],
    "_collections._tuplegetter": ["__new__", "__repr__", "__get__", "__set__", "__delete__", "__reduce__"],
    "_collections._deque_iterator": ["__new__", "__iter__", "__next__", "__length_hint__", "__reduce__"],
    "_collections._deque_reverse_iterator": ["__new__", "__iter__", "__next__", "__length_hint__", "__reduce__"],
    "functools.partial": ["__new__", "__repr__", "__call__", "__setattr__", "__delattr__", "__get__", "__reduce__", "__setstate__", "__class_getitem__"],
    "functools._lru_cache_wrapper": ["__new__", "__call__", "__get__", "cache_info", "cache_clear", "__reduce__", "__copy__", "__deepcopy__"],
    "functools.KeyWrapper": ["__call__", "__lt__", "__le__", "__eq__", "__ne__", "__gt__", "__ge__"],
    "operator.attrgetter": ["__new__", "__repr__", "__call__", "__reduce__"],
    "operator.itemgetter": ["__new__", "__repr__", "__call__", "__reduce__"],
    "operator.methodcaller": ["__new__", "__repr__", "__call__", "__reduce__"],
    "_thread.lock": ["__new__", "__repr__", "acquire_lock", "acquire", "release_lock", "release", "locked_lock", "locked", "__enter__", "__exit__", "_at_fork_reinit"],
    "_thread.RLock": ["__new__", "__repr__", "acquire", "release", "locked", "_is_owned", "_acquire_restore", "_release_save", "_recursion_count", "__enter__", "__exit__", "_at_fork_reinit"],
    "_thread._local": ["__new__", "__getattribute__", "__setattr__", "__delattr__"],
    "weakref.ReferenceType": ["__new__", "__repr__", "__hash__", "__call__", "__eq__", "__ne__", "__init__", "__class_getitem__"],
    "weakref.ProxyType": ["__repr__", "__str__", "__setattr__", "__delattr__", "__lt__", "__le__", "__eq__", "__ne__", "__gt__", "__ge__", "__iter__", "__next__", "__add__", "__radd__", "__sub__", "__rsub__", "__mul__", "__rmul__", "__mod__", "__rmod__", "__divmod__", "__rdivmod__", "__pow__", "__rpow__", "__neg__", "__pos__", "__abs__", "__bool__", "__invert__", "__lshift__", "__rlshift__", "__rshift__", "__rrshift__", "__and__", "__rand__", "__xor__", "__rxor__", "__or__", "__ror__", "__int__", "__float__", "__iadd__", "__isub__", "__imul__", "__imod__", "__ipow__", "__ilshift__", "__irshift__", "__iand__", "__ixor__", "__ior__", "__floordiv__", "__rfloordiv__", "__truediv__", "__rtruediv__", "__ifloordiv__", "__itruediv__", "__index__", "__matmul__", "__rmatmul__", "__imatmul__", "__len__", "__getitem__", "__setitem__", "__delitem__", "__contains__", "__bytes__", "__reversed__"],
    "weakref.CallableProxyType": ["__repr__", "__call__", "__str__", "__setattr__", "__delattr__", "__lt__", "__le__", "__eq__", "__ne__", "__gt__", "__ge__", "__iter__", "__next__", "__add__", "__radd__", "__sub__", "__rsub__", "__mul__", "__rmul__", "__mod__", "__rmod__", "__divmod__", "__rdivmod__", "__pow__", "__rpow__", "__neg__", "__pos__", "__abs__", "__bool__", "__invert__", "__lshift__", "__rlshift__", "__rshift__", "__rrshift__", "__and__", "__rand__", "__xor__", "__rxor__", "__or__", "__ror__", "__int__", "__float__", "__iadd__", "__isub__", "__imul__", "__imod__", "__ipow__", "__ilshift__", "__irshift__", "__iand__", "__ixor__", "__ior__", "__floordiv__", "__rfloordiv__", "__truediv__", "__rtruediv__", "__ifloordiv__", "__itruediv__", "__index__", "__matmul__", "__rmatmul__", "__imatmul__", "__len__", "__getitem__", "__setitem__", "__delitem__", "__contains__"],
    "os.stat_result": ["__new__", "__repr__", "__reduce__", "__replace__"],
    "os.terminal_size": ["__new__", "__repr__", "__reduce__", "__replace__"],
    "os.times_result": ["__new__", "__repr__", "__reduce__", "__replace__"],
    "os.uname_result": ["__new__", "__repr__", "__reduce__", "__replace__"],
    "os.statvfs_result": ["__new__", "__repr__", "__reduce__", "__replace__"],
    "os.waitid_result": ["__new__", "__repr__", "__reduce__", "__replace__"],
    "types.SimpleNamespace": ["__new__", "__repr__", "__eq__", "__init__", "__reduce__", "__replace__"],
    "types.GenericAlias": ["__new__", "__repr__", "__hash__", "__call__", "__eq__", "__ne__", "__iter__", "__or__", "__ror__", "__getitem__", "__mro_entries__", "__instancecheck__", "__subclasscheck__", "__reduce__", "__dir__"],
    "types.UnionType": ["__repr__", "__hash__", "__lt__", "__le__", "__eq__", "__ne__", "__gt__", "__ge__", "__or__", "__ror__", "__getitem__", "__mro_entries__", "__class_getitem__"],
    "builtins.property": ["__new__", "__get__", "__set__", "__delete__", "__init__", "getter", "setter", "deleter", "__set_name__"],
    "builtins.staticmethod": ["__new__", "__call__", "__get__", "__init__"],
    "builtins.classmethod": ["__new__", "__get__", "__init__"],
    "builtins.map": ["__new__", "__iter__", "__next__"],
    "builtins.filter": ["__new__", "__iter__", "__next__"],
    "builtins.zip": ["__new__", "__iter__", "__next__"],
    "builtins.enumerate": ["__new__", "__iter__", "__next__"],
    "builtins.reversed": ["__new__", "__iter__", "__next__", "__length_hint__"]
}
CLASSES = {"itertools.accumulate": itertools.accumulate, "itertools.batched": itertools.batched, "itertools.chain": itertools.chain, "itertools.combinations": itertools.combinations,
           "itertools.combinations_with_replacement": itertools.combinations_with_replacement, "itertools.compress": itertools.compress, "itertools.count": itertools.count,
           "itertools.cycle": itertools.cycle, "itertools.dropwhile": itertools.dropwhile, "itertools.filterfalse": itertools.filterfalse, "itertools.groupby": itertools.groupby,
           "itertools.islice": itertools.islice, "itertools.pairwise": itertools.pairwise, "itertools.permutations": itertools.permutations, "itertools.product": itertools.product,
           "itertools.repeat": itertools.repeat, "itertools.starmap": itertools.starmap, "itertools.takewhile": itertools.takewhile, "itertools.zip_longest": itertools.zip_longest,
           "collections.deque": collections.deque, "collections.defaultdict": collections.defaultdict, "_collections._tuplegetter": _collections._tuplegetter,
           "_collections._deque_iterator": _collections._deque_iterator, "_collections._deque_reverse_iterator": _collections._deque_reverse_iterator,
           "functools.partial": functools.partial, "functools._lru_cache_wrapper": functools._lru_cache_wrapper, "functools.KeyWrapper": key_wrapper,
           "operator.attrgetter": operator.attrgetter, "operator.itemgetter": operator.itemgetter, "operator.methodcaller": operator.methodcaller,
           "_thread.lock": _thread.LockType, "_thread.RLock": _thread.RLock, "_thread._local": _thread._local,
           "weakref.ReferenceType": weakref.ReferenceType, "weakref.ProxyType": weakref.ProxyType, "weakref.CallableProxyType": weakref.CallableProxyType,
           "os.stat_result": os.stat_result, "os.terminal_size": os.terminal_size, "os.times_result": os.times_result, "os.uname_result": os.uname_result,
           "os.statvfs_result": os.statvfs_result, "os.waitid_result": os.waitid_result,
           "types.SimpleNamespace": types.SimpleNamespace, "types.GenericAlias": types.GenericAlias, "types.UnionType": types.UnionType,
           "builtins.property": property, "builtins.staticmethod": staticmethod, "builtins.classmethod": classmethod, "builtins.map": map, "builtins.filter": filter,
           "builtins.zip": zip, "builtins.enumerate": enumerate, "builtins.reversed": reversed}
SAMPLES = {"itertools.accumulate": lambda: itertools.accumulate([1]), "itertools.batched": lambda: itertools.batched([1], 1), "itertools.chain": lambda: itertools.chain(),
           "itertools.combinations": lambda: itertools.combinations([1], 1), "itertools.combinations_with_replacement": lambda: itertools.combinations_with_replacement([1], 1),
           "itertools.compress": lambda: itertools.compress([], []), "itertools.count": lambda: itertools.count(), "itertools.cycle": lambda: itertools.cycle([]),
           "itertools.dropwhile": lambda: itertools.dropwhile(bool, []), "itertools.filterfalse": lambda: itertools.filterfalse(None, []), "itertools.groupby": lambda: itertools.groupby([]),
           "itertools.islice": lambda: itertools.islice([], 1), "itertools.pairwise": lambda: itertools.pairwise([]), "itertools.permutations": lambda: itertools.permutations([]),
           "itertools.product": lambda: itertools.product(), "itertools.repeat": lambda: itertools.repeat(1), "itertools.starmap": lambda: itertools.starmap(max, []),
           "itertools.takewhile": lambda: itertools.takewhile(bool, []), "itertools.zip_longest": lambda: itertools.zip_longest(),  # type: ignore[call-overload]
           "collections.deque": lambda: collections.deque(), "collections.defaultdict": lambda: collections.defaultdict(), "_collections._tuplegetter": lambda: _collections._tuplegetter(0, "d"),
           "_collections._deque_iterator": lambda: iter(collections.deque()), "_collections._deque_reverse_iterator": lambda: reversed(collections.deque()),
           "functools.partial": lambda: functools.partial(max), "functools._lru_cache_wrapper": lambda: functools.lru_cache(None)(max), "functools.KeyWrapper": lambda: functools.cmp_to_key(compare)(1),
           "operator.attrgetter": lambda: operator.attrgetter("x"), "operator.itemgetter": lambda: operator.itemgetter(0), "operator.methodcaller": lambda: operator.methodcaller("x"),
           "_thread.lock": lambda: _thread.allocate_lock(), "_thread.RLock": lambda: _thread.RLock(), "_thread._local": lambda: _thread._local(), "weakref.ReferenceType": lambda: weakref.ref(referent),
           "os.stat_result": lambda: os.stat_result(range(10)), "os.terminal_size": lambda: os.terminal_size((1, 2)), "os.times_result": lambda: os.times_result(range(5)),
           "os.uname_result": lambda: os.uname_result(("a", "b", "c", "d", "e")), "os.statvfs_result": lambda: os.statvfs_result(range(10)), "os.waitid_result": lambda: os.waitid_result(range(5)),
           "types.SimpleNamespace": lambda: types.SimpleNamespace(), "types.UnionType": lambda: int | str,
           "builtins.property": lambda: property(), "builtins.staticmethod": lambda: staticmethod(max), "builtins.classmethod": lambda: classmethod(max), "builtins.map": lambda: map(max, []),  # type: ignore[arg-type]
           "builtins.filter": lambda: filter(None, []), "builtins.zip": lambda: zip(), "builtins.enumerate": lambda: enumerate([]), "builtins.reversed": lambda: reversed(Sequence())}


def show_method(owner_name, cls, name, value, sample):  # type: ignore[no-untyped-def]
    kind = type(value).__name__
    print(owner_name, name, kind, addressless(repr(value)), value.__name__, value.__qualname__, callable(value), isinstance(value, types.FunctionType), isinstance(value, types.WrapperDescriptorType), isinstance(value, types.MethodDescriptorType))  # type: ignore[no-untyped-call]
    if kind == "builtin_function_or_method":
        print(value.__self__ is cls, value.__module__, failed(value), failed(lambda: value(1)), failed(lambda: value(int) if cls is not int else value(str)))  # type: ignore[no-untyped-call]
        return
    print(value.__objclass__ is cls, failed(value), failed(lambda: value(1)), value.__get__(sample) == getattr(sample, name), failed(lambda: value.__get__(None, None)))  # type: ignore[no-untyped-call]
    bound = getattr(sample, name)
    print(type(bound).__name__, addressless(repr(bound)).replace(repr(sample), "SAMPLE"), bound.__name__, bound.__qualname__, bound == getattr(sample, name), hash(bound) == hash(getattr(sample, name)), callable(bound), isinstance(bound, types.MethodWrapperType), isinstance(bound, types.BuiltinFunctionType), isinstance(bound, types.MethodType))  # type: ignore[no-untyped-call]
    if kind != "classmethod_descriptor":
        print(bound.__self__ is sample)
    else:
        print(bound.__self__ is type(sample))


for owner_name, names in METHODS.items():
    cls = CLASSES[owner_name]
    print(owner_name, failed(lambda: object.__new__(cls)), failed(lambda: tuple.__new__(cls)), failed(lambda: dict.__new__(cls)))  # type: ignore[no-untyped-call]
    if owner_name not in SAMPLES:
        for name in names:
            value = vars(cls)[name]
            print(owner_name, name, type(value).__name__, addressless(repr(value)), value.__name__, value.__qualname__)  # type: ignore[no-untyped-call]
        continue
    sample = SAMPLES[owner_name]()  # type: ignore[no-untyped-call]
    for name in names:
        show_method(owner_name, cls, name, vars(cls)[name], sample)  # type: ignore[no-untyped-call]

# ---- the built-in types the runtime writes in C++
for cls, name, sample in ((int, "__add__", 1), (int, "__repr__", 1), (bool, "__and__", True), (str, "__repr__", "a"), (str, "join", "a"), (list, "__iter__", []), (list, "append", []), (tuple, "__len__", ()), (dict, "__getitem__", {}), (dict, "get", {}),
                          (object, "__init__", object()), (object, "__repr__", object()), (float, "__add__", 1.5), (complex, "__add__", 1j), (bytes, "__add__", b""), (set, "add", set()), (range, "__iter__", range(1)), (slice, "indices", slice(1)),
                          (BaseException, "__str__", ValueError()), (BaseException, "with_traceback", ValueError()), (dict, "fromkeys", {}), (int, "from_bytes", 1), (int, "__new__", 1), (object, "__new__", object()), (dict, "__new__", {})):
    show_method(cls.__name__, cls, name, vars(cls)[name], sample)  # type: ignore[no-untyped-call]
print(types.WrapperDescriptorType, types.MethodWrapperType, types.MethodDescriptorType, types.ClassMethodDescriptorType, types.BuiltinFunctionType, types.WrapperDescriptorType.__name__, types.MethodWrapperType.__name__, type(object.__init__) is types.WrapperDescriptorType, type(object().__init__) is types.MethodWrapperType, type(str.join) is types.MethodDescriptorType, type(dict.__dict__["fromkeys"]) is types.ClassMethodDescriptorType, type("".join) is types.BuiltinFunctionType)  # type: ignore[misc]
print(failed(lambda: type("X", (types.WrapperDescriptorType,), {})), failed(lambda: type("X", (types.MethodWrapperType,), {})), failed(lambda: types.WrapperDescriptorType()), failed(lambda: types.MethodWrapperType()), failed(lambda: setattr(int.__add__, "__name__", "x")), failed(lambda: setattr((1).__add__, "__name__", "x")), failed(lambda: setattr(int.__add__, "x", 1)), failed(lambda: setattr((1).__add__, "x", 1)))  # type: ignore[no-untyped-call]
print((1).__add__ == (1).__add__, (1).__add__ == (2).__add__, (1).__add__ == (1).__sub__, (1).__add__ != (1).__add__, int.__add__ == int.__add__, int.__add__ == int.__sub__, int.__add__ is int.__add__, str.join is str.join, "a".join == "a".join, "a".join == "b".join, failed(lambda: (1).__add__ < (1).__add__))  # type: ignore[no-untyped-call,operator]

# ---- what a class written in Python makes of them
class Counted(itertools.count):  # type: ignore[type-arg]
    def __next__(self):  # type: ignore[no-untyped-def]
        return super().__next__() + 100


class Partial(functools.partial):  # type: ignore[type-arg]
    def __call__(self, *args):  # type: ignore[no-untyped-def]
        return ("called", super().__call__(*args))


class Queue(collections.deque):  # type: ignore[type-arg]
    def append(self, value):  # type: ignore[no-untyped-def]
        super().append(value * 2)


class Default(collections.defaultdict):  # type: ignore[type-arg]
    def __missing__(self, key):  # type: ignore[no-untyped-def]
        return ("missing", key)


class Fresh(itertools.count):  # type: ignore[type-arg]
    def __new__(cls):  # type: ignore[no-untyped-def]
        return super().__new__(cls, 5)


print(next(Counted(1)), Partial(max, 1)(2), type(Counted.__next__).__name__, type(Counted(1).__next__).__name__, type(Counted.__iter__).__name__, type(Counted(1).__iter__).__name__, type(Counted.__new__).__name__, Counted.__new__ is itertools.count.__new__, Counted.__iter__ is itertools.count.__iter__, next(Fresh()), failed(lambda: object.__new__(Fresh)), failed(lambda: object.__new__(Counted)))  # type: ignore[no-untyped-call]
queue = Queue()
queue.append(2)  # type: ignore[no-untyped-call]
print(list(queue), type(Queue.append).__name__, type(collections.deque.append).__name__, type(queue.extend).__name__, Default()[1], Default.__missing__ is not collections.defaultdict.__missing__)
for receiver in (itertools.count.__next__, collections.deque.append, itertools.chain.__dict__["from_iterable"]):
    print(failed(lambda: receiver()), failed(lambda: receiver(1)), failed(lambda: receiver(None)))  # type: ignore[arg-type,call-arg,no-untyped-call]
print(list(itertools.chain.__dict__["from_iterable"](itertools.chain, [[1], [2]])), failed(lambda: itertools.chain.__dict__["from_iterable"](int, [])), failed(lambda: itertools.chain.__dict__["from_iterable"](1, [])), list(itertools.chain.__dict__["from_iterable"].__get__(None, itertools.chain)([[3]])), list(itertools.chain.__dict__["from_iterable"].__get__(itertools.chain())([[4]])), failed(lambda: itertools.chain.__dict__["from_iterable"].__get__(None, int)), failed(lambda: itertools.chain.__dict__["from_iterable"].__get__(1)), type(dict.fromkeys).__name__, dict.__dict__["fromkeys"](dict, "a"), failed(lambda: dict.__dict__["fromkeys"](int, "a")), failed(lambda: dict.__dict__["fromkeys"](1, "a")))  # type: ignore[no-untyped-call]
print(next(itertools.count.__next__.__get__(itertools.count(5)).__self__), itertools.count.__next__.__get__(itertools.count(5))(), itertools.count.__next__(itertools.count(6)), collections.deque.__len__(collections.deque([1])), collections.deque.append.__get__(collections.deque())(1), repr(itertools.count.__new__.__self__), itertools.count.__new__(itertools.count, 3).__next__())  # type: ignore[attr-defined]
