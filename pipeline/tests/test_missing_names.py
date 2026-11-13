"""The names CPython has and the runtime lacks (tools/missing_names.py, conformance/names-baseline.txt), and what left that list on
2026-11-13, compiled, against CPython: the callables' and the singletons' own slots as attributes, the docstrings of slot wrappers
and of the built-in types' methods, the containers' __repr__ as the slot wrapper it is, and four names of four modules."""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import textwrap
from pathlib import Path

from pipeline.build import build
from pipeline.tests.test_review_2026_11_03 import same

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from tools.missing_names import BASELINE, measure  # noqa: E402

# Each kind's own slots, called through the type and through the object, with no, one and two arguments, another object of the kind,
# an int and None, a wrong self, and a keyword: method_richcompare and method_hash, meth_richcompare, wrapper_richcompare, NoneType's
# _Py_BaseObject_RichCompare, and tp_call and tp_repr under their wrappers
OWN_SLOTS = r"""
import re, sys
class K:
    def m(self, *args, **kwds):
        return ("m", args, kwds)
    def n(self):
        return "n"
def f(*args, **kwds):
    return ("f", args, kwds)
def g():
    return "g"
k = K()
def show(value):
    return re.sub(r"0x[0-9a-f]+", "0x", repr(value))
def attempt(thunk):
    try:
        return show(thunk())
    except BaseException as exc:
        return type(exc).__name__ + ": " + re.sub(r"0x[0-9a-f]+", "0x", str(exc))
SAMPLES = [("None", None, None, 1), ("NotImplemented", NotImplemented, NotImplemented, 1), ("Ellipsis", ..., ..., 1),
           ("method", k.m, k.m, k.n), ("function", f, f, g), ("builtin", len, len, repr), ("builtin method", [].append, [].append, {}.get),
           ("method-wrapper", (1).__add__, (1).__add__, (2).__add__), ("wrapper_descriptor", int.__add__, int.__add__, int.__sub__),
           ("method_descriptor", list.append, list.append, list.pop), ("classmethod_descriptor", dict.fromkeys, dict.fromkeys, bytes.fromhex),
           ("getset_descriptor", int.real, int.real, int.imag), ("member_descriptor", slice.start, slice.start, slice.stop)]
NAMES = ["__call__", "__repr__", "__hash__", "__eq__", "__ne__", "__lt__", "__le__", "__gt__", "__ge__", "__bool__"]
for label, obj, same, other in SAMPLES:
    t = type(obj)
    for name in NAMES:
        if name not in vars(t):
            print(label, name, "not its own")
            continue
        own = vars(t)[name]
        rows = [type(own).__name__, type(getattr(obj, name)).__name__]
        mask = name == "__hash__" and label != "None"
        for args in ((), (same,), (other,), (1,), (None,), (same, same)):
            if name == "__call__" and label in ("method", "function") and args == ():
                rows.append(attempt(lambda: own(obj, 1, key=2)))
            if name == "__call__" and label not in ("method", "function") and len(args) != 1:
                continue                          # a built-in called with no or two arguments: its own errors, not this table's
            if name == "__call__" and label in ("method-wrapper", "wrapper_descriptor", "method_descriptor", "classmethod_descriptor", "getset_descriptor", "member_descriptor", "None", "NotImplemented", "Ellipsis") and args != (1,):
                continue
            rows.append("<hash>" if mask and args == () and attempt(lambda: own(obj)).lstrip("-").isdigit() else attempt(lambda: own(obj, *args)))
        rows.append(attempt(lambda: own()))
        rows.append(attempt(lambda: own(object())))
        rows.append(attempt(lambda: getattr(obj, name)(key=1)))
        print(label, name, *rows)
print(attempt(lambda: K.m.__call__(k, 1)), attempt(lambda: k.m.__call__(1, a=2)), attempt(lambda: f.__call__.__call__(3)), attempt(lambda: len.__call__([1, 2])),
      attempt(lambda: [].append.__call__(1)), attempt(lambda: list.append.__call__([], 1)), attempt(lambda: (1).__add__.__call__(2)), attempt(lambda: int.__add__.__call__(1, 2)),
      attempt(lambda: dict.fromkeys.__call__("ab")), attempt(lambda: type(f).__call__(f, 1)), attempt(lambda: type(k.m).__call__(k.m, 1)))
print(k.m == k.m, k.m == K().m, hash(k.m) == hash(k.m), k.m.__eq__(k.m), k.m.__eq__(k.n), k.m.__ne__(k.m), k.m.__lt__(k.m), len.__eq__(len), len.__ne__(repr), [].append.__eq__([].append),
      (1).__add__.__eq__((1).__add__), (1).__add__ == (1).__add__, (1).__add__.__eq__((2).__add__), hash((1).__add__) == hash((1).__add__), hash(len) == hash(len), None.__eq__(None), None.__ne__(None), None.__ne__(1),
      None.__lt__(None), None.__bool__(), None.__hash__() == hash(None), NotImplemented.__repr__(), (...).__repr__(), None.__repr__(), f.__repr__() == repr(f), k.m.__repr__() == repr(k.m))
"""

# list's, tuple's, dict's, set's and frozenset's __repr__ are the prelude's functions under CPython's slot wrapper
CONTAINERS_REPR = r"""
for t in (list, tuple, dict, set, frozenset):
    v = vars(t)["__repr__"]
    print(t.__name__, type(v).__name__, type(t.__repr__).__name__, type(t().__repr__).__name__, t.__repr__.__name__, t.__repr__.__qualname__, t.__repr__.__objclass__ is t, t.__repr__.__doc__, t().__repr__.__doc__, t.__repr__(t()), repr(t.__repr__))
"""

FOUR_NAMES = r"""
import warnings, zlib, _ast, _locale, builtins, ast
def m(f):
    try:
        return repr(f())
    except BaseException as e:
        return type(e).__name__ + ": " + str(e)
class S(str):
    pass
print(type(zlib.__getattr__).__name__, zlib.__getattr__.__doc__, zlib.__getattr__.__name__, zlib.__getattr__.__module__, "__getattr__" in vars(zlib))
print(m(lambda: zlib.__getattr__()), m(lambda: zlib.__getattr__("x")), m(lambda: zlib.__getattr__("x", "y")), m(lambda: zlib.__getattr__(1)), m(lambda: zlib.__getattr__(name="x")),
      m(lambda: zlib.__getattr__("__version__", x=1)), m(lambda: zlib.nope), m(lambda: getattr(zlib, "nope", 5)), hasattr(zlib, "nope"), hasattr(zlib, "__version__") if False else None)
with warnings.catch_warnings(record=True) as caught:
    warnings.simplefilter("always")
    print(zlib.__version__, zlib.__getattr__(S("__version__")), getattr(zlib, "__version__"), [(str(w.message), w.category.__name__, w.lineno) for w in caught])
try:
    zlib.nope
except AttributeError as e:
    print(e.name, e.obj is zlib, e.args)
try:
    from zlib import nope
except ImportError as e:
    print(type(e).__name__, e.name, e.name_from)
warnings.simplefilter("error")
print(m(lambda: zlib.__version__))
warnings.simplefilter("always")
print(type(_ast._is_abstract).__name__, _ast._is_abstract.__doc__, _ast._is_abstract.__name__, _ast._is_abstract.__module__, _ast._is_abstract.__qualname__,
      [n for n in sorted(vars(_ast)) if isinstance(getattr(_ast, n), type) and _ast._is_abstract(getattr(_ast, n))], _ast._is_abstract(int), _ast._is_abstract(5), _ast._is_abstract(ast.AST),
      _ast._is_abstract(ast.Constant), _ast._is_abstract(None), _ast._is_abstract((ast.AST,)))
print(m(lambda: _ast._is_abstract()), m(lambda: _ast._is_abstract(1, 2)), m(lambda: _ast._is_abstract(cls=int)), m(lambda: _ast._is_abstract([])), m(lambda: _ast._is_abstract(set())),
      m(lambda: _ast._is_abstract({})), m(lambda: _ast._is_abstract(frozenset())))
class Odd:
    def __hash__(self):
        raise ValueError("no hash")
class Sub(TypeError):
    pass
class Odder:
    def __hash__(self):
        raise Sub("a subclass's")
print(m(lambda: _ast._is_abstract(Odd())), m(lambda: _ast._is_abstract(Odder())))
try:
    _ast._is_abstract([])
except TypeError as e:
    print(e.__context__, e.__cause__, e.__suppress_context__)
print(_locale._DATE_FMT, "_DATE_FMT" in vars(_locale), builtins.__debug__, "__debug__" in vars(builtins), __debug__, type(builtins.__debug__).__name__)
"""

# A C type that names tp_getattro itself, as the generic function object has: its own __getattribute__ wrapper over object's
# (collections, itertools, functools.partial, operator's getters, struct.Struct, unicodedata.UCD, ast.AST with __setattr__ and
# __delattr__ too); and a native module's own __getattr__, which answers only for names CPython's module does not have
GENERIC_ATTRIBUTE_SLOTS = r"""
import ast, collections, functools, itertools, operator, struct, unicodedata, _struct, _tokenize, zlib
def m(f):
    try:
        return repr(f())
    except BaseException as e:
        return type(e).__name__ + ": " + str(e)
SAMPLES = [collections.deque([1]), collections.defaultdict(int), iter(collections.deque([1])), reversed(collections.deque([1])), functools.partial(len), itertools.chain(),
           itertools.count(), itertools.cycle([1]), itertools.repeat(1), itertools.accumulate([1]), itertools.batched([1], 1), itertools.combinations([1], 1),
           itertools.combinations_with_replacement([1], 1), itertools.compress([1], [1]), itertools.dropwhile(len, []), itertools.takewhile(len, []), itertools.filterfalse(len, []),
           itertools.groupby([1]), next(itertools.groupby([1]))[1], itertools.islice([1], 1), itertools.pairwise([1]), itertools.permutations([1]), itertools.product([1]),
           itertools.starmap(len, []), itertools.zip_longest([1]), itertools.tee([1])[0], operator.attrgetter("a"), operator.itemgetter(1), operator.methodcaller("a"),
           struct.Struct("b"), unicodedata.ucd_3_2_0, ast.Pass(), ast.Name("x")]
for obj in SAMPLES:
    t = type(obj)
    owner = next(c for c in t.__mro__ if "__getattribute__" in vars(c))
    own = vars(owner)["__getattribute__"]
    print(t.__name__, owner.__name__, type(own).__name__, type(obj.__getattribute__).__name__, own.__objclass__ is owner, own.__name__, own.__qualname__, own.__doc__,
          own(obj, "__class__") is t, own(obj, "__doc__") == t.__doc__, m(lambda: own(obj, "nope")), m(lambda: own(obj, 5)), m(lambda: own(obj)), m(lambda: own(obj, "a", "b")),
          m(lambda: own(5, "real")), m(lambda: own()), m(lambda: obj.__getattribute__(name="x")), type(obj.__getattribute__("__class__")).__name__)
node = ast.Name("x")
ast.AST.__setattr__(node, "left", 5)
print(node.left, type(vars(ast.AST)["__setattr__"]).__name__, type(vars(ast.AST)["__delattr__"]).__name__, ast.AST.__setattr__.__objclass__ is ast.AST, m(lambda: ast.AST.__setattr__(5, "a", 1)),
      m(lambda: ast.AST.__setattr__(node, 5, 1)), m(lambda: ast.AST.__delattr__(node, "left")), hasattr(node, "left"), m(lambda: ast.AST.__delattr__(node, "left")),
      m(lambda: node.__setattr__("x")), ast.AST.__setattr__.__doc__, ast.AST.__delattr__.__doc__)
print(m(lambda: zlib.nope), m(lambda: zlib.__getattr__("nope")), hasattr(zlib, "nope"))
"""

# cell_richcompare (by what the cells hold, an empty one before anything else), no hash, and cell_repr
CELLS = r"""
import re, types
def m(f):
    try:
        return re.sub(r"0x[0-9a-f]+", "0x", repr(f()))
    except BaseException as e:
        return type(e).__name__ + ": " + re.sub(r"0x[0-9a-f]+", "0x", str(e))
def cell(value):
    return (lambda: value).__closure__[0]
one, uno, two, text, empty, nothing = cell(1), cell(1), cell(2), cell("a"), types.CellType(), types.CellType()
CELLS = {"one": one, "uno": uno, "two": two, "text": text, "empty": empty, "nothing": nothing}
t = type(one)
print(sorted(n for n in vars(t) if n in ("__eq__", "__ne__", "__lt__", "__le__", "__gt__", "__ge__", "__hash__", "__repr__", "__new__", "cell_contents")), vars(t)["__hash__"],
      type(vars(t)["__eq__"]).__name__, type(one.__eq__).__name__, type(vars(t)["__repr__"]).__name__)
for a in CELLS:
    for b in CELLS:
        x, y = CELLS[a], CELLS[b]
        print(a, b, m(lambda: x == y), m(lambda: x != y), m(lambda: x < y), m(lambda: x <= y), m(lambda: x > y), m(lambda: x >= y), m(lambda: x.__eq__(y)), m(lambda: x.__lt__(y)),
              m(lambda: t.__ge__(x, y)))
print(m(lambda: one == 1), m(lambda: one != 1), m(lambda: one < 1), m(lambda: one.__eq__(1)), m(lambda: one.__lt__(None)), m(lambda: 1 == one), m(lambda: one == None),
      m(lambda: t.__eq__(1, one)), m(lambda: one.__eq__()), m(lambda: one.__eq__(one, one)), m(lambda: one.__eq__(other=one)))
print(m(lambda: hash(one)), m(lambda: {one}), m(lambda: {one: 1}), m(lambda: one.__hash__), m(lambda: one in [uno]), m(lambda: [one, two, uno].count(one)), m(lambda: sorted([two, one, empty], key=None) == [empty, one, two]),
      m(lambda: max(one, two) is two), m(lambda: min([two, empty, one]) is empty))
print(m(lambda: repr(one)), m(lambda: repr(text)), m(lambda: repr(empty)), m(lambda: one.__repr__()), m(lambda: str(empty)), m(lambda: t.__repr__(1)), m(lambda: f"{empty}"),
      m(lambda: repr(cell(None))), m(lambda: repr(cell([]))), m(lambda: repr(cell(one))))
class Named:
    pass
Named.__name__ = "N" * 100
print(m(lambda: repr(cell(Named()))), m(lambda: cell(Named()) == cell(Named())), m(lambda: cell([1]) == cell([1])), m(lambda: cell([1]) < cell([2])), m(lambda: cell(1.0) == one), m(lambda: cell(float("nan")) == cell(float("nan"))))
"""

# every slot wrapper and every method of these types that the runtime has: its kind and its docstring
DOCS = r"""
import builtins, collections, functools, io, itertools, re, types, weakref
TYPES = [object, type, int, bool, float, complex, str, bytes, bytearray, list, tuple, dict, set, frozenset, range, slice, property, staticmethod, classmethod, super,
         enumerate, reversed, zip, map, filter, BaseException, type(None), type(NotImplemented), type(...), types.FunctionType, types.MethodType, types.ModuleType,
         types.GeneratorType, types.MappingProxyType, types.SimpleNamespace, collections.deque, collections.OrderedDict, collections.defaultdict, functools.partial, io.StringIO,
         io.BytesIO, itertools.chain, itertools.count, re.Pattern, re.Match, weakref.ref, weakref.ProxyType, weakref.CallableProxyType, type(iter([])), type({}.keys()),
         type(len), type(list.append), type(int.__add__), type((1).__add__)]
for t in TYPES:
    for name, v in sorted(vars(t).items()):
        kind = type(v).__name__
        if kind in ("wrapper_descriptor", "method_descriptor", "classmethod_descriptor"):
            print(repr((t.__module__ + "." + t.__qualname__, name, kind, v.__doc__, getattr(t, name).__doc__)))
class K:
    pass
class L(list):
    pass
@functools.wraps(dict.__getitem__)
def wrapped(*args):
    return dict.__getitem__(*args)
print(repr(("summary", [].__len__.__doc__, (1).__add__.__doc__, "".__mod__.__doc__, K().__init__.__doc__, K.__repr__.__doc__, object.__init__.__doc__, type([].__len__).__name__,
            weakref.ProxyType.__iadd__.__doc__, list.__iadd__.__doc__, type(list.__iadd__.__doc__).__name__, int.__add__.__doc__ == float.__add__.__doc__, [].append.__doc__,
            "".join.__doc__, {}.get.__doc__, dict.fromkeys.__doc__, (1).to_bytes.__doc__, str.maketrans.__doc__, wrapped.__doc__, wrapped.__name__, wrapped.__qualname__,
            wrapped({1: 2}, 1), functools.wraps(str.upper)(lambda s: s).__doc__, L.append.__doc__ == list.append.__doc__, L().append.__doc__, L.__len__.__doc__,
            L().__add__.__doc__)))
"""


# how a range, a slice, the two named singletons and the callables say they are made again: each answer, through the object and the type
REDUCE = r"""
import collections, copy, functools, math, os, sys, types
def m(f):
    try:
        return f()
    except BaseException as e:
        return type(e).__name__ + ": " + str(e)
class K:
    def meth(self):
        return "meth"
    def __private(self):
        return "private"
    def reach(self):
        return self.__private
    @classmethod
    def cm(cls):
        return "cm"
    @staticmethod
    def sm():
        return "sm"
    def __repr__(self):
        return "K()"
class _Lead(K):
    def __mine(self):
        return "mine"
    def own(self):
        return self.__mine
class ___:
    def __u(self):
        return "u"
    def own(self):
        return self.__u
    def __repr__(self):
        return "___()"
class Slotted:
    __slots__ = ("x", "__y")
class Named:
    __name__ = 5
    def __call__(self, *a):
        return a
class StrName(str):
    pass
class NamedSub:
    __name__ = StrName("__sub")
    def __call__(self, *a):
        return a
def f():
    pass
k, items, queue = K(), [1], collections.deque([2])
VALUES = [range(1, 10, 2), range(2**70), slice(1, None, k), ..., NotImplemented, len, math.sqrt, print, sys.exit, os.getcwd, os.stat, functools.reduce, items.append, "ab".upper,
          (5).bit_length, dict.fromkeys, str.maketrans, bytes.maketrans, int.from_bytes, queue.append, None.__format__, k.__dir__, object.__new__, list.__new__, k.meth, k.reach(),
          K.cm, _Lead().own(), _Lead().reach(), ___().own(), types.MethodType(len, items), types.MethodType(Named(), k), types.MethodType(NamedSub(), k),
          types.MethodType(functools.partial(len), k), types.MethodType(K, 1), (1).__add__, k.__init__, items.__len__, None.__eq__, list.append,
          int.__add__, slice.start, Slotted.x, vars(Slotted)["_Slotted__y"], collections.deque.append, object.__init__, type.__call__, functools.partial.func]
for v in VALUES:
    t = type(v)
    print(t.__name__, "__reduce__" in vars(t), m(lambda: v.__reduce__()), m(lambda: v.__reduce_ex__(4)), m(lambda: v.__reduce_ex__(0)), m(lambda: t.__reduce__(v)))
    for bad in (lambda: v.__reduce__(1), lambda: v.__reduce__(x=1), lambda: t.__reduce__(), lambda: t.__reduce__(v, 1), lambda: t.__reduce_ex__(v), lambda: v.__reduce_ex__("a")):
        print("   ", m(bad))
for t in (range, slice, type(...), type(NotImplemented), type(len), type(k.meth), type((1).__add__), type(list.append), type(int.__add__), type(slice.start)):
    d = vars(t)["__reduce__"]
    print(t.__name__, type(d).__name__, repr(d), d.__name__, d.__qualname__, d.__objclass__ is t, d.__doc__, m(lambda: d(5)), m(lambda: d(k)), m(lambda: d(f)), m(lambda: d(None)))
for v in (int.real, vars(dict)["fromkeys"], f, None, sys, type, K, k, property(), staticmethod(f), super(K, k), iter(()).__reduce__):
    print(type(v).__name__, "__reduce__" in vars(type(v)), m(lambda: v.__reduce__())[:60] if isinstance(m(lambda: v.__reduce__()), str) else "made")
print(str.maketrans.__self__, bytes.maketrans.__self__, dict.fromkeys.__self__, object.__new__.__self__, len.__self__ is sys.modules["builtins"], math.sqrt.__self__ is math, items.append.__self__ is items,
      None.__format__.__self__, K.sm.__call__.__self__ is K.sm, f.__call__.__reduce__()[1] == (f, "__call__"), K.sm.__call__.__reduce__()[1][0] is K.sm, f.__call__.__reduce__()[0] is getattr)
for v in (k.meth, k.reach(), K.cm, _Lead().own(), ___().own(), (1).__add__, items.__len__, list.append, int.__add__, slice.start, Slotted.x, items.append, len, range(3), slice(1), ..., NotImplemented):
    c, d = m(lambda: copy.copy(v)), m(lambda: copy.deepcopy(v))
    print(type(v).__name__, c is v, c == v, d is v, d == v if type(v).__name__ != "method" else d(), m(lambda: getattr(c, "__self__", None) is getattr(v, "__self__", None)))
for bad in (types.MethodType(len, items), types.MethodType(functools.partial(len), k), types.MethodType(Named(), k)):
    print(m(lambda: copy.copy(bad)), m(lambda: copy.deepcopy(bad)) if not isinstance(m(lambda: copy.deepcopy(bad)), types.MethodType) else "a method")
"""


# a mappingproxy's `|` on either side, `|=`, reversed() and comparisons, with CPython's words
PROXY = r"""
import collections, types
def m(f):
    try:
        return f()
    except BaseException as e:
        return type(e).__name__ + ": " + str(e)
class K:
    marker = 1
class Ror:
    def __ror__(self, other):
        return ("ror", type(other).__name__)
class Declines:
    def __or__(self, other):
        print("  asked with", type(other).__name__)
        return NotImplemented
    __ror__ = __or__
class Table:
    def __getitem__(self, key):
        return key
    def __len__(self):
        return 1
    def __iter__(self):
        return iter([1])
    def __repr__(self):
        return "Table()"
    def __hash__(self):
        return 11
class Peek:
    def __eq__(self, other):
        print("  compared with", type(other).__name__)
        return NotImplemented
    __hash__ = None
def ior(a, b):
    a |= b
    return a
backing = {1: 2}
P = types.MappingProxyType
mp, od, fd, tb, cls = P(backing), P(collections.OrderedDict(a=1)), P(frozendict(a=1)), P(Table()), vars(K)
others = [{3: 4}, mp, od, fd, 5, None, "a", [(1, 2)], {1}, frozenset({1}), {1: 2}.keys(), {1: 2}.items(), {1: 2}.values(), int, 1.5, Ror(), Declines(), object(), collections.OrderedDict(b=2),
          frozendict(b=2), collections.ChainMap({9: 9}), collections.Counter("ab"), types.SimpleNamespace(), list[int], int | str]
def shown(v):
    if isinstance(v, (dict, frozendict)) and "marker" in v:
        return (type(v).__name__, sorted((repr(k) for k in v if not str(k).startswith("__") or k == "__doc__")))
    if isinstance(v, (set, frozenset)):
        return (type(v).__name__, sorted(map(repr, v)))
    return v
for proxy in (mp, od, fd, tb, cls):
    print(type(proxy).__name__, type(m(lambda: proxy.copy())).__name__)
    for other in others:
        if type(other).__name__ in ("object", "Ror", "Declines"):
            print(" ", type(other).__name__, shown(m(lambda: proxy | other)), "/", shown(m(lambda: other | proxy)), "/", shown(m(lambda: ior(proxy, other))), "/", shown(m(lambda: proxy.__or__(other))), "/", shown(m(lambda: proxy.__ror__(other))))
        else:
            print(" ", shown(m(lambda: proxy | other)), "/", shown(m(lambda: other | proxy)), "/", shown(m(lambda: ior(proxy, other))), "/", shown(m(lambda: ior(type(other)(other) if isinstance(other, (dict, set)) else other, proxy))),
                  "/", shown(m(lambda: proxy.__or__(other))), "/", shown(m(lambda: proxy.__ror__(other))), "/", m(lambda: proxy.__ior__(other)))
    for name in ("__or__", "__ror__", "__ior__", "__lt__", "__le__", "__gt__", "__ge__", "__eq__", "__ne__"):
        d = vars(P)[name]
        print(" ", name, type(d).__name__, d.__doc__, m(lambda: getattr(proxy, name)()), m(lambda: getattr(proxy, name)(1, 2)), m(lambda: d({}, {})), m(lambda: d()), m(lambda: getattr(proxy, name)(x=1)),
              shown(m(lambda: getattr(proxy, name)(proxy))) if name not in ("__ior__",) else "-", m(lambda: getattr(proxy, name)(5)) if name not in ("__or__", "__ror__", "__ior__") else "-")
    d = vars(P)["__reversed__"]
    print("  __reversed__", type(d).__name__, d.__doc__, m(lambda: [k for k in reversed(proxy) if not str(k).startswith("__")]), m(lambda: type(proxy.__reversed__()).__name__), m(lambda: proxy.__reversed__(1)),
          m(lambda: d({})), m(lambda: d()), m(lambda: proxy.__reversed__(x=1)))
    for sym, f in (("<", lambda a, b: a < b), ("<=", lambda a, b: a <= b), (">", lambda a, b: a > b), (">=", lambda a, b: a >= b), ("==", lambda a, b: a == b), ("!=", lambda a, b: a != b)):
        print(" ", sym, m(lambda: f(proxy, proxy)), m(lambda: f(proxy, {})), m(lambda: f({}, proxy)), m(lambda: f(proxy, 5)), m(lambda: f(5, proxy)), m(lambda: f(proxy, Peek())), m(lambda: f(Peek(), proxy)))
    print("  hash", m(lambda: hash(proxy)) if proxy is not fd else hash(proxy) == hash(frozendict(a=1)), m(lambda: proxy.__hash__()) if proxy is not fd else proxy.__hash__() == hash(frozendict(a=1)))
print(backing, K.marker, sorted(k for k in vars(K) if not k.startswith("__")), UnicodeTranslateError("abc", 0, 1, "why").encoding)
e = UnicodeTranslateError("abc", 0, 1, "why")
e.encoding = "set"
print(e.encoding, str(e), vars(UnicodeTranslateError)["encoding"].__doc__, m(lambda: UnicodeTranslateError.encoding.__get__(5)))
del e.encoding
print(e.encoding)
"""


# the five members of a Unicode error (PyMember_SetOne over UnicodeError_members) and what str() makes of them: three objects that can be
# anything or deleted, two numbers that are ints and stay, the reason asked for its str() before the encoding, the object checked last
UNICODE_ERRORS = r"""
def m(f):
    try:
        return f()
    except BaseException as e:
        return type(e).__name__ + ": " + str(e)
def gone(e, name):
    delattr(e, name)
    return getattr(e, name)
for make in (lambda: UnicodeEncodeError("ascii", "abc", 0, 1, "why"), lambda: UnicodeDecodeError("ascii", b"abc", 0, 1, "why"), lambda: UnicodeTranslateError("abc", 0, 1, "why")):
    for name in ("encoding", "object", "start", "end", "reason"):
        e = make()
        print(type(e).__name__, name, m(lambda: gone(e, name)), m(lambda: gone(e, name)), m(lambda: str(e)), m(lambda: setattr(e, name, 5)), m(lambda: getattr(e, name)), m(lambda: str(e)))
class Loud:
    def __init__(self, name):
        self.name = name
    def __str__(self):
        print("  str of", self.name)
        return self.name
for make in (lambda: UnicodeEncodeError("ascii", "abc", 0, 1, "why"), lambda: UnicodeDecodeError("ascii", b"abc", 0, 1, "why"), lambda: UnicodeTranslateError("abc", 0, 1, "why")):
    e = make()
    e.reason, e.encoding = Loud("reason"), Loud("encoding")
    print(str(e))
    for bad in ("x", 1.5, None, 2**70, True, -3):
        print(m(lambda: setattr(e, "start", bad)), m(lambda: e.start), m(lambda: setattr(e, "end", bad)), m(lambda: e.end), type(e.start).__name__, m(lambda: str(e)))
    e = make()
    for obj in ("zz", b"zz", bytearray(b"zz"), 5, None, "", b""):
        e.object = obj
        print(repr(obj), m(lambda: str(e)))
    e = make()
    e.start, e.end = 0, 3
    print(str(e), type(vars(type(e))["start"]).__name__, vars(type(e))["start"].__doc__, vars(type(e))["encoding"].__doc__, e.args)
    class Drops:
        def __str__(self):
            del e.object
            return "dropped"
    e.reason = Drops()
    print(m(lambda: str(e)), e.object)
"""


# the six types whose comparison is == and != only, by name and by operator, with every arity; ~ on a bool with its warning
DECLINED = r"""
import contextvars, types, typing, warnings, weakref

def m(f):
    try:
        return f()
    except BaseException as e:
        return type(e).__name__ + ": " + str(e)

class K:
    pass
k = K()
P = typing.ParamSpec("P")
samples = {"ns": (types.SimpleNamespace(a=1), types.SimpleNamespace(a=1), types.SimpleNamespace(a=2)), "ref": (weakref.ref(k), weakref.ref(k), weakref.ref(K)),
           "ctx": (contextvars.copy_context(), contextvars.copy_context(), contextvars.Context()), "args": (P.args, P.args, typing.ParamSpec("Q").args),
           "kwargs": (P.kwargs, P.kwargs, typing.ParamSpec("Q").kwargs), "ga": (list[int], list[int], list[str])}
for label, (a, same, other) in samples.items():
    t = type(a)
    print(label, t.__name__, [n for n in ("__eq__", "__ne__", "__lt__", "__le__", "__gt__", "__ge__", "__hash__") if n in vars(t)],
          sorted({type(vars(t)[n]).__name__ for n in ("__eq__", "__ne__", "__lt__", "__le__", "__gt__", "__ge__") if n in vars(t)}))
    for name in ("__eq__", "__ne__", "__lt__", "__le__", "__gt__", "__ge__"):
        f = vars(t).get(name)
        if f is None:
            print("  ", name, "absent")
            continue
        print("  ", name, m(lambda: f(a, same)), m(lambda: f(a, other)), m(lambda: f(a, 5)), m(lambda: f(a)), m(lambda: f(5, a)), m(lambda: f(a, a, a)), f.__doc__)
    print("  ", m(lambda: a < same), m(lambda: a <= 5), m(lambda: 5 > a), m(lambda: a == same), m(lambda: a != other), m(lambda: a == 5))
with warnings.catch_warnings(record=True) as w:
    warnings.simplefilter("always")
    print(~True, ~False, True.__invert__(), bool.__invert__(False), m(lambda: bool.__invert__(5)), m(lambda: True.__invert__(1)), type(vars(bool)["__invert__"]).__name__, vars(bool)["__invert__"].__doc__,
          int.__invert__(True), ~int(True), [(x.category.__name__, str(x.message), x.lineno) for x in w][:1], len(w))
class B(int):
    pass
print(~B(1))
warnings.simplefilter("error")
print(m(lambda: ~True))

import sys
def where(w):
    return [(x.category.__name__, str(x.message), x.lineno, x.filename.rpartition("/")[2]) for x in w]
with warnings.catch_warnings(record=True) as w:
    warnings.simplefilter("always")
    a = ~True
    b = True.__invert__()
    c = bool.__invert__(False)
    import operator
    d = operator.invert(True)
    e = [~flag for flag in (True, False)]
    print(a, b, c, d, e, where(w))
warnings.resetwarnings()
warnings.simplefilter("default")
import io
buffer = io.StringIO()
real, sys.stderr = sys.stderr, buffer
try:
    for _ in range(2):
        x = ~True
    y = ~False
finally:
    sys.stderr = real
print("\n".join(line.rpartition("/")[2] if "prog.py:" in line else line for line in buffer.getvalue().splitlines()))
"""


def test_the_names_the_runtime_lacks_are_the_listed_ones() -> None:
    """A name that goes missing fails here, and one that arrives is taken off the list (python tools/missing_names.py --update)."""
    if shutil.which("g++") is None:
        return
    found, listed = measure(), BASELINE.read_text(encoding="utf-8").split()
    assert found == listed, f"missing now: {sorted(set(found) - set(listed))}; there now: {sorted(set(listed) - set(found))}"


def test_the_callables_and_the_singletons_own_slots() -> None:
    same(OWN_SLOTS)


def test_the_containers_repr_is_a_slot_wrapper() -> None:
    same(CONTAINERS_REPR)


def test_four_names_of_four_modules() -> None:
    same(FOUR_NAMES)


def test_the_generic_attribute_slots_a_c_type_names_itself() -> None:
    same(GENERIC_ATTRIBUTE_SLOTS)


def test_a_cell_compares_by_what_it_holds() -> None:
    same(CELLS)


def test_how_the_callables_are_made_again() -> None:
    same(REDUCE)


def test_a_mappingproxys_operators() -> None:
    same(PROXY)


def test_a_unicode_errors_members() -> None:
    same(UNICODE_ERRORS)


def test_comparisons_that_decline_and_a_bool_inverted() -> None:
    same(DECLINED)


def test_a_proxys_hash_is_its_mappings_whatever_the_seed() -> None:
    """A hash is 64 bits, and a small int holds 63: the proxy's own hash was cut for most seeds."""
    if shutil.which("g++") is None:
        return
    with tempfile.TemporaryDirectory() as tmp:
        prog = Path(tmp, "prog.py")
        prog.write_text("import types\nfor m in (frozendict(a=1), frozendict(), frozendict({'k': (1, 'x'), 2.5: None})):\n"
                        "    print(hash(types.MappingProxyType(m)) == hash(m), types.MappingProxyType(m).__hash__() == m.__hash__())\n", encoding="utf-8")
        exe = build(prog, "prog.py")
        for seed in range(12):
            got = subprocess.run([str(exe)], capture_output=True, text=True, check=False, env=dict(os.environ, PYTHONHASHSEED=str(seed)), cwd=tmp)
            assert got.stdout == "True True\n" * 3, (seed, got.stdout, got.stderr)


def test_the_docstrings_of_slot_wrappers_and_methods() -> None:
    """Every row the compiled program prints is CPython's row; the rows it does not print are names the list of missing names has
    (the table's scope is the type's tp_name, which for these types is the qualified name without `builtins.`)."""
    if shutil.which("g++") is None:
        return
    with tempfile.TemporaryDirectory() as tmp:
        prog = Path(tmp, "prog.py")
        prog.write_text(textwrap.dedent(DOCS), encoding="utf-8")
        env = dict(os.environ, PYTHONHASHSEED="0")
        ref = subprocess.run([sys.executable, str(prog)], capture_output=True, text=True, check=False, env=env, cwd=tmp)
        got = subprocess.run([str(build(prog, "prog.py"))], capture_output=True, text=True, check=False, env=env, cwd=tmp)
    assert (got.returncode, ref.returncode) == (0, 0), got.stderr + ref.stderr
    want = {row[:2]: row for row in map(eval, ref.stdout.splitlines())}
    have = {row[:2]: row for row in map(eval, got.stdout.splitlines())}
    assert len(have) > 900 and set(have) <= set(want), sorted(set(have) - set(want))
    assert all(have[key] == want[key] for key in have), [(have[key], want[key]) for key in have if have[key] != want[key]][:5]
    listed = set(BASELINE.read_text(encoding="utf-8").split())
    unlisted = [key for key in sorted(set(want) - set(have)) if not any(f"{scope}:{key[1]}" in listed for scope in (key[0], key[0].removeprefix("builtins."), key[0].rpartition(".")[2]))]
    # a static method of a built-in type is the builtin itself in the type's dict here, where CPython's dict holds a staticmethod
    # (str.maketrans, bytes.maketrans, bytearray.maketrans: TODO), so the row's kind differs and the program does not print it
    assert unlisted == [], unlisted


if __name__ == "__main__":
    test_the_names_the_runtime_lacks_are_the_listed_ones()
    test_the_callables_and_the_singletons_own_slots()
    test_the_containers_repr_is_a_slot_wrapper()
    test_four_names_of_four_modules()
    test_the_generic_attribute_slots_a_c_type_names_itself()
    test_a_cell_compares_by_what_it_holds()
    test_the_docstrings_of_slot_wrappers_and_methods()
