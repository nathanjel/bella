# clause: C-3-44
# spec: section 3
# status: P1
# source: Objects/typeobject.c (type_new_alloc, inherit_special, inherit_patma_flags), Modules/_abc.c
"""type.__flags__: a built-in type's, and a class's from its bases, its __slots__, its abstract methods and what abc registers."""
# ruff: noqa: ANN001, ANN002, ANN003, ANN201, ANN202, ANN204, B018, B023, B024, E501, E731, E742, PLR0133, SLF001
import _thread
import abc
import collections
import collections.abc
import functools
import itertools
import os
import sys
import types


class A:
    pass


class B(A):
    pass


class S:
    __slots__ = ()


class S2:
    __slots__ = ("a",)


class S3(S2):
    pass


class SD:
    __slots__ = ("__dict__",)


class SW:
    __slots__ = ("__weakref__",)


class SB:
    __slots__ = ("__dict__", "__weakref__")


class Sl(S):
    __slots__ = ()


class D(dict):  # type: ignore[type-arg]
    pass


class DS(dict):  # type: ignore[type-arg]
    __slots__ = ()


class T(tuple):  # type: ignore[type-arg]
    pass


class T2(tuple):  # type: ignore[type-arg]
    __slots__ = ()


class I(int):
    pass


class I2(int):
    __slots__ = ()


class F(float):
    pass


class C(complex):
    pass


class E(Exception):
    pass


class E2(Exception):
    __slots__ = ()


class OS(OSError):
    pass


class M(type):
    pass


class MC(type):
    def __call__(cls):  # type: ignore[no-untyped-def]
        return 1


class MS(M):
    pass


class WithMeta(metaclass=M):
    pass


class X(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    def f(self):  # type: ignore[no-untyped-def]
        pass


class XC(X):
    def f(self):  # type: ignore[no-untyped-def]
        pass


class Xs(abc.ABC):
    __slots__ = ()


class Sq(collections.abc.Sequence):  # type: ignore[type-arg]
    def __getitem__(self, i):  # type: ignore[no-untyped-def]
        return 0

    def __len__(self):  # type: ignore[no-untyped-def]
        return 0


class Mp(collections.abc.Mapping):  # type: ignore[type-arg]
    def __getitem__(self, i):  # type: ignore[no-untyped-def]
        return 0

    def __len__(self):  # type: ignore[no-untyped-def]
        return 0

    def __iter__(self):  # type: ignore[no-untyped-def]
        return iter(())


class Reg:
    pass


class RegChild(Reg):
    pass


class RegM:
    pass


class Both(Sq, Mp):
    pass


class Both2(Mp, Sq):
    pass


class Marked(metaclass=abc.ABCMeta):
    __abc_tpflags__ = 1 << 5


class MarkedChild(Marked):
    pass


class Plain2(A, S):
    pass


class WithCall:
    def __call__(self):  # type: ignore[no-untyped-def]
        return 1


class WithGet:
    def __get__(self, a, b):  # type: ignore[no-untyped-def]
        return 1


class WithDel:
    def __del__(self):  # type: ignore[no-untyped-def]
        pass


class WithMatch:
    __match_args__ = ("a",)


class DeqSub(collections.deque):  # type: ignore[type-arg]
    pass


class DD(collections.defaultdict):  # type: ignore[type-arg]
    pass


class Part(functools.partial):  # type: ignore[type-arg]
    pass


class Prop(property):
    pass


collections.abc.Sequence.register(Reg)
collections.abc.Mapping.register(RegM)
collections.abc.Sequence.register(RegM)
for cls in (A, B, S, S2, S3, SD, SW, SB, Sl, D, DS, T, T2, I, I2, F, C, E, E2, OS, M, MC, MS, WithMeta, X, XC, Xs, Sq, Mp, Reg, RegChild, RegM, Both, Both2, Marked, MarkedChild, Plain2, WithCall, WithGet, WithDel, WithMatch, DeqSub, DD, Part, Prop, abc.ABC, abc.ABCMeta, collections.abc.Sequence, collections.abc.Mapping, collections.abc.Set, collections.abc.Hashable):
    print(cls.__name__, hex(cls.__flags__), type(cls.__flags__).__name__)  # type: ignore[arg-type]
for cls in (object, type, int, bool, str, bytes, bytearray, float, complex, list, tuple, dict, set, frozenset, range, slice, property, staticmethod, classmethod, super, type(None), type(NotImplemented), type(...), BaseException, Exception, OSError, ValueError, StopIteration, type(len), type(lambda: 0), type(iter([])), type(sys), map, zip, filter, enumerate, reversed,  # type: ignore[assignment]
            type(int.__add__), type((1).__add__), type(str.join), type("".join), type({}.keys()), type(iter({})), itertools.count, itertools.chain, collections.deque, collections.defaultdict, functools.partial, os.stat_result, os.terminal_size, _thread.LockType, _thread.RLock, _thread._local, types.SimpleNamespace, types.GenericAlias, types.UnionType, types.MappingProxyType, types.CellType, types.ModuleType, types.GeneratorType):
    print(cls.__name__, hex(cls.__flags__))  # type: ignore[arg-type]
print(isinstance(int.__flags__, int), A.__flags__ & (1 << 9) != 0, int.__flags__ & (1 << 9) != 0, type.__dict__["__flags__"].__name__, type(type.__dict__["__flags__"]).__name__)
try:
    A.__flags__ = 1  # type: ignore[misc]
except AttributeError as exc:
    print(type(exc).__name__)
try:
    class Bad(metaclass=abc.ABCMeta):
        __abc_tpflags__ = (1 << 5) | (1 << 6)
except TypeError as exc:
    print(type(exc).__name__)
print(hex(Marked.__flags__), "__abc_tpflags__" in vars(Marked), "__abc_tpflags__" in vars(MarkedChild))
collections.abc.Sequence.register(Marked)
print(hex(Marked.__flags__), hex(MarkedChild.__flags__))
collections.abc.Mapping.register(MarkedChild)
print(hex(Marked.__flags__), hex(MarkedChild.__flags__), hex(RegM.__flags__), hex(RegChild.__flags__))
collections.abc.Sequence.register(int)
print(hex(int.__flags__))


class LateChild(Reg):
    pass


print(hex(LateChild.__flags__))
