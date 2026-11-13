# clause: C-3-69
# spec: section 3 (the data model: what a type has of its own), section 6 (builtins)
# status: P1
# source: Objects/object.c (NoneType, NotImplementedType, ellipsis), Objects/classobject.c (method), Objects/funcobject.c,
#         Objects/methodobject.c, Objects/descrobject.c (the descriptors and the method-wrapper), Objects/typeobject.c (slotdefs)
"""What the singletons and the callables have of their own, asked for by name: None's comparisons, which are object's but
NoneType's own; a bound method's, a built-in's and a method-wrapper's equality and hash (the same function of the same
object); `__call__` and `__repr__` of each kind, which do what calling and repr() do; the docstring of a slot's wrapper,
which is the slot's and so the same for every type, and of a built-in type's method; and the containers' `__repr__`, a
slot wrapper like any other."""
import ast
import builtins
import functools
import warnings
import zlib
from collections.abc import Callable

import _ast


class K:
    def m(self, *args: object, **kwds: object) -> tuple[object, ...]:
        return ("m", args, kwds)

    def n(self) -> str:
        return "n"


class L(list):  # type: ignore[type-arg]
    pass


def f(*args: object, **kwds: object) -> tuple[object, ...]:
    return ("f", args, kwds)


def attempt(thunk: Callable[[], object]) -> str:
    try:
        result = thunk()
    except Exception as exc:  # noqa: BLE001  # which exception, by class
        return type(exc).__name__
    return ascii(result)


k = K()
items: list[int] = []
none_type = type(None)
print("None's own:", none_type.__eq__(None, None), none_type.__eq__(None, 1), None.__ne__(None), None.__ne__(1), None.__lt__(None), None.__ge__(None),  # type: ignore[call-arg, operator]
      None.__bool__(), None.__repr__(), None.__hash__() == hash(None), type(none_type.__eq__).__name__, type(None.__eq__).__name__,
      [n for n in ("__eq__", "__ne__", "__lt__", "__le__", "__gt__", "__ge__", "__hash__", "__repr__", "__bool__") if n not in vars(none_type)],
      attempt(lambda: none_type.__eq__(1, None)), attempt(lambda: None.__eq__()), attempt(lambda: None.__eq__(1, 2)))  # type: ignore[call-arg]
print("the other two:", NotImplemented.__repr__(), (...).__repr__(), type(NotImplemented.__repr__).__name__, attempt(lambda: NotImplemented.__bool__()))
bound = k.m
print("a method's own:", bound.__call__(1, key=2), type(bound).__call__(bound, 3), bound.__eq__(k.m), bound.__eq__(k.n), bound.__eq__(1), bound.__ne__(K().m),  # type: ignore[operator]
      bound.__lt__(bound), bound.__hash__() == hash(k.m), bound == k.m, bound is k.m, bound.__repr__() == repr(bound), type(bound.__eq__).__name__,  # type: ignore[operator]
      type(type(bound).__call__).__name__, attempt(lambda: type(bound).__call__(f)), attempt(lambda: type(bound).__eq__(bound)))
print("a function's own:", f.__call__(1, key=2), type(f).__call__(f), f.__call__.__call__(3), f.__repr__() == repr(f), type(f.__call__).__name__,  # type: ignore[operator]
      type(type(f).__call__).__name__, attempt(lambda: type(f).__call__(len)), "__eq__" in vars(type(f)), "__hash__" in vars(type(f)))
append = items.append
print("a built-in's own:", len.__call__([1, 2]), append.__call__(1), items, len.__eq__(len), len.__eq__(repr), len.__ne__(len), len.__lt__(len), append.__eq__(items.append),  # type: ignore[operator]
      append.__eq__([].append), len.__hash__() == hash(len), len.__repr__(), type(len.__call__).__name__, type(type(len).__eq__).__name__,  # type: ignore[operator]
      attempt(lambda: type(len).__call__(f)), sorted(n for n in ("__call__", "__eq__", "__hash__", "__repr__", "__lt__") if n in vars(type(len))))
add = (1).__add__
print("a wrapper's own:", add.__call__(2), int.__add__.__call__(1, 2), list.append.__call__(items, 5), dict.fromkeys.__call__("ab"), add.__eq__((1).__add__),  # type: ignore[operator]
      add.__eq__((2).__add__), add.__eq__((1).__sub__), add == (1).__add__, add.__hash__() == hash((1).__add__), int.__add__.__repr__(), list.append.__repr__(),
      dict.fromkeys.__repr__().startswith("<built-in method fromkeys of type object at "), int.real.__repr__(), slice.start.__repr__(), type(add.__call__).__name__, attempt(lambda: int.__add__.__call__("a", 1)),  # type: ignore[operator]
      "__eq__" in vars(type(int.__add__)), "__eq__" in vars(type(add)))
print("a slot's docstring:", int.__add__.__doc__, float.__add__.__doc__, add.__doc__, list.__iadd__.__doc__, list.__len__.__doc__, object.__init__.__doc__ == K.__init__.__doc__,
      L.__len__.__doc__, L().__add__.__doc__, type(list.__repr__.__doc__).__name__)
print("a method's docstring:", list.append.__doc__, append.__doc__, L.append.__doc__, dict.get.__doc__, type(str.join.__doc__).__name__, dict.fromkeys.__doc__ == {}.fromkeys.__doc__,
      functools.wraps(dict.__getitem__)(lambda d, key: d[key]).__doc__, functools.wraps(str.upper)(lambda s: s).__name__)
print("the containers' repr:", [type(vars(t)["__repr__"]).__name__ for t in (list, tuple, dict, set, frozenset)], type(items.__repr__).__name__,
      list.__repr__.__objclass__ is list, list.__repr__([1]), dict.__repr__({1: 2}), list.__repr__.__qualname__, repr(set.__repr__), L.__repr__ is list.__repr__,  # type: ignore[attr-defined]
      L.__repr__(L([1])), attempt(lambda: list.__repr__((1,))))
with warnings.catch_warnings(record=True) as caught:
    warnings.simplefilter("always")
    version = zlib.__version__  # type: ignore[attr-defined]
print("four names:", builtins.__debug__, __debug__, type(zlib.__getattr__).__name__, version, [w.category.__name__ for w in caught], attempt(lambda: zlib.nope),  # type: ignore[attr-defined]
      hasattr(zlib, "nope"), attempt(lambda: zlib.__getattr__()), _ast._is_abstract(ast.expr), _ast._is_abstract(ast.BinOp), _ast._is_abstract(int),  # type: ignore[attr-defined, call-arg]
      attempt(lambda: _ast._is_abstract([])), attempt(lambda: _ast._is_abstract()))  # type: ignore[attr-defined]
