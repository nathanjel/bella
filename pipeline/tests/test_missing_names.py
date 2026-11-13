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
    test_the_docstrings_of_slot_wrappers_and_methods()
