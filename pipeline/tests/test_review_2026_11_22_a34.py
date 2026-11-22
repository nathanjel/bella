"""Review A34 of 2026-11-22 (range 6bd852a..9966dbe), compiled against CPython: a program for each finding fixed.

Codex's Astra at low effort read the fixes of review A33. The review log has its 23 findings as RL-754 to RL-776: the next
layer of the rule that a prelude stands for C. A type's name is the runtime's to give (`_type_name`, `_class_name`,
`_type_fullname`, `_class_fullname`: no `__name__`, `__qualname__` or `__module__` of a class is read as an attribute, which a
metaclass answers; RL-754, RL-767); a name a program gave is its characters where the C formats it with %U (RL-758, RL-762);
a chained error's context is stored, not assigned (`_set_context`, RL-759); an iterator is taken once (`_tp_iter`, RL-765);
and the reprs of an ast node and of a SimpleNamespace follow their C step by step (RL-766, RL-768 to RL-770, RL-774,
RL-775). RL-756 waits for the author, RL-776 for the Struct step.

Run under pytest or directly: python3 -m pipeline.tests.test_review_2026_11_22_a34
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from pipeline.tests.test_repr_text import ITS_OWN_AGAIN, ITS_OWN_PYTHON, STANDS_FOR_C
from pipeline.tests.test_review_2026_11_19 import same

PRELUDE = Path(__file__).resolve().parent.parent.parent / "runtime" / "prelude"

# sys.unraisablehook's argument type, taken from a real report
HOOK_ARGS = r'''
import sys
kinds = []
sys.unraisablehook = lambda args: kinds.append(type(args))
class _D:
    def __del__(self): raise KeyError
_x = _D()
del _x
sys.unraisablehook = sys.__unraisablehook__
Args = kinds[0]
'''

FINDINGS: list[tuple[str, str, str]] = [
    ('RL-754', "a type's full name asks nothing of the class's __module__", r'''
import operator, weakref
class S(str):
    def __eq__(self, other):
        print("  eq")
        raise LookupError
    __hash__ = str.__hash__
class H:
    def __length_hint__(self): return -1
for module in (S("mod"), None, 7, "builtins", "__main__", "pkg.mod"):
    H.__module__ = module
    try: operator.length_hint(H())
    except Exception as e: print(type(module).__name__, type(e).__name__)
class K: pass
k = K()
for module in (S("mod"), None, "pkg"):
    K.__module__ = module
    try: print(repr(weakref.proxy(k)).split(" at ")[0], repr(weakref.ref(k)).split("'")[1])
    except Exception as e: print(type(e).__name__)
'''),
    ('RL-755', "a class's __name__ and __qualname__ are the objects a program assigned", r'''
import collections
class S(str): pass
class C: pass
s, q = S("custom"), S("Outer.custom")
C.__name__ = s
C.__qualname__ = q
print(type(C.__name__).__name__, C.__name__ is s, type(C.__qualname__).__name__, C.__qualname__ is q, repr(C), type(C()).__name__ is s)
C.__name__ = "plain"
C.__qualname__ = "Plain"
print(type(C.__name__).__name__, C.__name__, type(C.__qualname__).__name__, repr(C))
for value in ("a\0b", 5, None):
    try: C.__name__ = value
    except Exception as e: print(type(e).__name__)
    try: C.__qualname__ = value
    except Exception as e: print(type(e).__name__)
class D(collections.deque): pass
class O(collections.OrderedDict): pass
class F(collections.defaultdict): pass
for kind in (D, O, F):
    kind.__name__ = S("Named")
    print(repr(kind()), kind.__name__ == "Named", type(kind.__name__).__name__)
'''),
    ('RL-757', "the default unraisable hook writes the object __repr__ returned", HOOK_ARGS + r'''
class S(str): pass
class Shown:
    def __repr__(self): return S("shown")
class Message:
    def __str__(self): return S("said")
class Sink:
    def write(self, s): print("  ", type(s).__name__, repr(s))
    def flush(self): print("   flush")
old = sys.stderr
for message, shown in (("report", Shown()), (Message(), Shown()), (Message(), None), (None, Shown())):
    sys.stderr = Sink()
    try:
        sys.__unraisablehook__(Args((ValueError, ValueError("v"), None, message, shown)))
    finally:
        sys.stderr = old
    print("returned")
'''),
    ('RL-758', "the reprs of type parameters take the name's characters", r'''
import typing
class S(str):
    def __radd__(self, other):
        print("  radd")
        return "other"
    def __add__(self, other):
        print("  add")
        return "other"
def show(value):
    text = repr(value)
    print(type(text).__name__, str.__str__(text))
show(typing.TypeVar(S("V")))
show(typing.TypeVar(S("V"), covariant=True))
show(typing.TypeVar(S("V"), infer_variance=True))
show(typing.ParamSpec(S("P")))
show(typing.TypeVarTuple(S("Ts")))
show(typing.ParamSpec(S("P")).args)
show(typing.ParamSpec(S("P")).kwargs)
print(type(typing.TypeVar(S("V")).__name__).__name__)
'''),
    ('RL-759', "a chained error's context is stored, whatever __setattr__ its class has", r'''
import codecs, io, json, sys
class Second(Exception):
    def __setattr__(self, name, value):
        print("  set", name, type(sys.exception()).__name__)
        raise ArithmeticError
def show(e):
    print(type(e).__name__, type(e.__context__).__name__, type(e.__cause__).__name__, e.__traceback__ is None)
class Key(str):
    def __repr__(self): raise Second
def fail(o): raise KeyError
try: raise OSError
except OSError:
    try: json.dumps({Key("k"): object()}, default=fail)
    except BaseException as e: show(e)
class Once:
    """close and flush raise the first time, so that the finalisers stay quiet."""
    failed = None
    def fail(self, error):
        if self.failed is None:
            self.failed = error
            raise error
class Raw(Once, io.BytesIO):
    def close(self): self.fail(Second())
class Buffered(Once, io.BufferedWriter):
    def flush(self): self.fail(KeyError())
try: Buffered(Raw()).close()
except BaseException as e: show(e)
class Half(Once, io.BytesIO):
    def __init__(self, error): self.error = error
    def close(self): self.fail(self.error)
    def readable(self): return True
    def writable(self): return True
try: io.BufferedRWPair(Half(Second()), Half(KeyError())).close()
except BaseException as e: show(e)
class Text(Once, io.TextIOWrapper):
    def flush(self): self.fail(KeyError())
try: Text(Raw()).close()
except BaseException as e: show(e)
class CtxError(Exception):
    def __setattr__(self, name, value):
        print("  setter", name)
        raise RuntimeError
class Dec(codecs.IncrementalDecoder):
    calls = 0
    def decode(self, data, final=False):
        Dec.calls += 1
        if Dec.calls > 1: raise IndexError
        return bytes(data).decode()
    def getstate(self): return b"", 0
    def setstate(self, state): raise CtxError
info = codecs.CodecInfo(None, None, incrementaldecoder=Dec, name="a34ctx")
codecs.register(lambda n: info if n == "a34ctx" else None)
class Buf(io.BytesIO):
    def writable(self): return False
f = io.TextIOWrapper(Buf(b"abc"), encoding="a34ctx", newline="\n")
f.read(1)
try: f.tell()
except BaseException as e: show(e)
class Note(Exception):
    @property
    def __notes__(self): return 42
    def __setattr__(self, name, value): print("  setter", name)
def encode(value, errors="strict"): raise Note
info2 = codecs.CodecInfo(encode, encode, name="a34note")
codecs.register(lambda n: info2 if n == "a34note" else None)
try: "x".encode("a34note")
except BaseException as e: show(e)
'''),
    ('RL-760', "the fallback of an unraisable report writes the colon and the text apart", HOOK_ARGS + r'''
class Bad(Exception):
    def __str__(self): raise LookupError
class Empty(Exception):
    def __str__(self): return ""
class Sink:
    def __init__(self, fail): self.n, self.fail = 0, fail
    def write(self, s):
        self.n += 1
        print("  ", self.n, type(s).__name__, repr(s))
        if self.n == self.fail: raise KeyError
    def flush(self): print("   flush")
old = sys.stderr
for error in (Bad(), Empty(), ValueError("v")):
    for fail in (3, 4, 5, 6):
        sys.stderr = Sink(fail)
        try:
            sys.__unraisablehook__(Args((type(error), error, None, "report", None)))
            sys.stderr = old
            print("returned")
        except BaseException as e:
            sys.stderr = old
            print("raised", type(e).__name__)
'''),
    ('RL-761', "str() of a SyntaxError is what str() of its message returned", r'''
class S(str): pass
class X:
    def __str__(self): return S("original")
for kind in (SyntaxError, IndentationError, TabError):
    for arguments in ((X(),), (X(), ("file.py", 3, 1, "text")), (X(), (None, None, None, None)), (X(), (None, 3, 1, "text")), (S("plain"),)):
        text = str(kind(*arguments))
        print(kind.__name__, type(text).__name__, str.__str__(text))
'''),
    ('RL-762', "the repr of a weak reference takes the name's characters", r'''
import weakref
class S(str):
    def __radd__(self, other):
        print("  radd")
        raise LookupError
def f(): pass
f.__name__ = S("myname")
class Named:
    __name__ = S("instance")
class Unnamed:
    __name__ = 7
kept = [f, Named(), Unnamed()]
for target in kept:
    try: print(repr(weakref.ref(target)).rpartition(" at ")[2].partition(" ")[2] or "no name")
    except Exception as e: print(type(e).__name__)
'''),
    ('RL-763', "a stream's repr cuts its type's name at 100 bytes", r'''
import io, os
for letter, count in (("é", 70), ("a", 120), ("€", 40), ("é", 50), ("x€", 40)):
    T = type(letter * count, (io.TextIOWrapper,), {})
    x = T(io.BytesIO(), encoding="utf-8")
    F = type(letter * count, (io.FileIO,), {})
    y = F(os.devnull)
    print(len(repr(x).split(" ")[0]), len(repr(y).split(" ")[0]))
    x.close()
    y.close()
'''),
    ('RL-764', "copy.copy of a StringIO, and what __setstate__ wants", r'''
import copy, io
class C(io.StringIO): pass
class Slots(io.StringIO): __slots__ = ("extra",)
for kind in (io.StringIO, C, Slots):
    source = kind("abc\ndef")
    source.read(2)
    try:
        y = copy.copy(source)
        print(kind.__name__, type(y).__name__, repr(y.getvalue()), y.tell(), y.read())
    except Exception as e: print(kind.__name__, type(e).__name__)
fresh = io.StringIO.__new__(io.StringIO)
for state in (("xy", "\n", 1, None), ("xy", "\n", 1, {"a": 1}), ("xy", "\n", -1, None), ("xy", "\n", 1.5, None), ("xy", "\n", 1, 5), ("xy",), 5, (b"xy", "\n", 0, None)):
    try:
        fresh.__setstate__(state)
        print("set", repr(fresh.getvalue()), fresh.tell())
    except Exception as e: print(type(e).__name__)
closed = io.StringIO()
closed.close()
try: closed.__setstate__(("xy", "\n", 1, None))
except ValueError: print("closed: ValueError")
'''),
    ('RL-765', "an iterator is asked for once", r'''
import collections, csv, functools, io
class I:
    """An iterator whose __iter__ counts: a second call raises."""
    def __init__(self, items): self.items, self.asked = list(items), 0
    def __iter__(self):
        self.asked += 1
        if self.asked > 1: raise ArithmeticError
        return self
    def __next__(self):
        if not self.items: raise StopIteration
        return self.items.pop(0)
def row(name, call):
    try: print(name, call())
    except Exception as e: print(name, type(e).__name__)
row("deque", lambda: collections.deque(I([1, 2])))
row("deque, no room", lambda: collections.deque(I([1, 2]), 0))
d = collections.deque()
row("extend", lambda: (d.extend(I([1, 2])), list(d))[1])
row("extendleft", lambda: (d.extendleft(I([3, 4])), list(d))[1])
row("count", lambda: sorted(collections.Counter(I("abca")).items()))
m = {}
row("_count_elements", lambda: (collections._count_elements(m, I("aab")), sorted(m.items()))[1])
row("reduce", lambda: functools.reduce(lambda a, b: a + b, I([1, 2, 3])))
row("reduce with a start", lambda: functools.reduce(lambda a, b: a + b, I([1, 2, 3]), 10))
row("sum", lambda: sum(I([1, 2, 3])))
row("sum of floats", lambda: sum(I([1.5, 2, 3.5])))
row("sum of anything", lambda: sum(I([[1], [2]]), []))
row("sum, complex", lambda: sum(I([1j, 2, 2.5])))
row("min", lambda: min(I([3, 1, 2])))
row("max with a key", lambda: max(I([3, 1, 2]), key=lambda v: -v))
out = io.StringIO()
row("csv writerow", lambda: (csv.writer(out).writerow(I(["a", "b"])), out.getvalue())[1])
b = io.BytesIO()
row("BytesIO.writelines", lambda: (b.writelines(I([b"a", b"b"])), b.getvalue())[1])
s = io.StringIO()
row("StringIO.writelines", lambda: (s.writelines(I(["a", "b"])), s.getvalue())[1])
'''),
    ('RL-766', "the repr of an ast node asks a sequence its length and two items", r'''
import ast
class L(list):
    def __len__(self):
        print("  len")
        return super().__len__()
    def __iter__(self):
        print("  iter")
        raise LookupError
    def __getitem__(self, i):
        print("  item", i)
        return super().__getitem__(i)
for value in (L([1, 2, 3]), L([1]), L([]), L([ast.Name("x"), 2])):
    try: print(repr(ast.Constant(value)))
    except Exception as e: print(type(e).__name__)
class Fields(ast.AST):
    _fields = L(["a", "b"])
node = ast.AST.__new__(Fields)
node.a, node.b = 1, 2
try: print(repr(node))
except Exception as e: print(type(e).__name__)
class Shrinks:
    def __repr__(self):
        del Shrinking._fields[1:]
        return "x"
class Shrinking(ast.AST):
    _fields = ["a", "b"]
node = ast.AST.__new__(Shrinking)
node.a, node.b = Shrinks(), 2
try: print(repr(node))
except Exception as e: print(type(e).__name__)
'''),
    ('RL-767', "a type's name is not asked of its metaclass", r'''
import ast, collections, functools, io, itertools, types
class M(type):
    @property
    def __name__(cls):
        print("  name asked")
        raise LookupError
    @property
    def __module__(cls):
        print("  module asked")
        raise LookupError
def show(make):
    try: print(repr(make()))
    except Exception as e: print(type(e).__name__)
class D(collections.deque, metaclass=M): pass
class F(collections.defaultdict, metaclass=M): pass
class O(collections.OrderedDict, metaclass=M): pass
class NS(types.SimpleNamespace, metaclass=M): pass
class A(ast.AST, metaclass=M): pass
class P(functools.partial, metaclass=M): pass
class Dict(dict, metaclass=M): pass
class List(list, metaclass=M): pass
class Set(set, metaclass=M): pass
class Frozen(frozenset, metaclass=M): pass
show(lambda: D([1]))
show(lambda: D([1], 3))
show(lambda: F(None, {1: 2}))
show(lambda: O({1: 2}))
show(lambda: O())
show(lambda: NS(a=1))
show(lambda: A())
show(lambda: Dict({1: 2}))
show(lambda: List([1]))
show(lambda: Set([1]))
show(lambda: Frozen([1]))
show(lambda: type("A.B", (collections.deque,), {})())
show(lambda: type("pkg.Name", (collections.OrderedDict,), {})())
show(lambda: type("pkg.Name", (types.SimpleNamespace,), {})(a=1))
for call in (lambda: collections.deque.__new__(M("X", (), {})), lambda: io.BytesIO().write(D()), lambda: len(itertools.count(D())),
             lambda: collections.deque.__repr__(NS()), lambda: types.SimpleNamespace.__repr__(D())):
    try: print(call())
    except Exception as e: print(type(e).__name__)
'''),
    ('RL-768', "the repr of a SimpleNamespace as its C makes it", r'''
from types import SimpleNamespace
def show(make):
    try: print(repr(make()))
    except Exception as e: print(type(e).__name__)
class Removes:
    def __repr__(self):
        del ns.b
        return "m"
ns = SimpleNamespace(a=Removes(), b=2)
show(lambda: ns)
class D(SimpleNamespace):
    @property
    def __dict__(self):
        print("  dict asked")
        raise RuntimeError
show(lambda: D())
show(lambda: D(a=1))
print(D(a=1) == D(a=1), D(a=1) != D(a=2), D(a=1).__reduce__()[1:], D(a=1).__replace__(b=2).__reduce__()[2])
class L(str):
    def __len__(self):
        print("  len asked")
        return 0
keyed = SimpleNamespace()
vars(keyed)[L("name")] = 1
show(lambda: keyed)
class X:
    @property
    def __class__(self):
        print("  class asked")
        return str
other = SimpleNamespace()
vars(other)[X()] = 1
vars(other)[""] = 2
vars(other)[5] = 3
show(lambda: other)
class N(SimpleNamespace):
    def __eq__(self, other):
        print("  eq asked")
        raise LookupError
show(lambda: N(a=N()))
loop = N()
loop.me = loop
show(lambda: loop)
'''),
    ('RL-771', "a type parameter's lazy evaluator takes a C int and reads a tuple's own items", r'''
import typing
class V:
    def __repr__(self):
        print("  repr asked")
        return "v"
class I(int):
    def __eq__(self, other):
        print("  eq asked")
        return True
    __hash__ = int.__hash__
class Index:
    def __index__(self): return 4
class T(tuple):
    def __iter__(self):
        print("  iter asked")
        raise LookupError
class Q:
    def __init__(self, qualname, module): self.__qualname__, self.__module__ = qualname, module
    def __repr__(self): return "q"
def show(call):
    try:
        result = call()
        print(result if type(result) is str else type(result).__name__)
    except Exception as e: print(type(e).__name__)
fn = typing.TypeVar("V", default=V()).evaluate_default
for fmt in (2**40, -(2**40), I(1), 1, 4, Index(), 1.5, "4", True):
    show(lambda: fn(fmt))
show(lambda: typing.TypeVar("V", default=T((int, str))).evaluate_default(4))
show(lambda: typing.TypeVar("V", default=T((int, str))).evaluate_default(1))
for qualname, module in ((None, "m"), ("name", None), ("name", "builtins"), ("name", "m"), (7, 8)):
    show(lambda: typing.TypeVar("V", default=Q(qualname, module)).evaluate_default(4))
'''),
    ('RL-774', "the repr of an ast node lets a field's value go before its repr is written, and enters its guard first", r'''
import ast
class Text(str):
    def __str__(self):
        print("  text.str")
        return "printed"
    def __del__(self): print("  text.del")
class Value:
    def __repr__(self):
        print("  value.repr")
        return Text("value")
    def __del__(self): print("  value.del")
class Node(ast.AST):
    _fields = ("x",)
    @property
    def x(self): return Value()
print(repr(Node()))
class M(type):
    entered = False
    @property
    def _fields(cls):
        print("  fields")
        if not cls.entered:
            cls.entered = True
            print("  nested", repr(node))
        return ()
class A(ast.AST, metaclass=M): pass
node = ast.AST.__new__(A)
print(repr(node))
'''),
]


def _c_lines(path: Path) -> list[tuple[int, str]]:
    """The lines of a prelude that stand for C: not the stand-ins a file defines for CPython's run of it (the block under
    `except NameError`), not importlib's own Python in bootstrap.py, not comments."""
    out: list[tuple[int, str]] = []
    stand_in = False
    stands_for_c = path.name != "bootstrap.py"
    for number, line in enumerate(path.read_text(encoding="utf-8").split("\n"), 1):
        if path.name == "bootstrap.py" and line.startswith(STANDS_FOR_C):
            stands_for_c = True
        elif path.name == "bootstrap.py" and line.startswith(ITS_OWN_AGAIN):
            stands_for_c = False
        if line.startswith("except NameError"):
            stand_in = True
        elif stand_in and line and line[0] not in " \t":
            stand_in = False
        if stands_for_c and not stand_in and not line.lstrip().startswith("#"):
            out.append((number, line.split("  #")[0]))
    return out


def _preludes() -> list[Path]:
    return [p for p in sorted(PRELUDE.glob("*.py")) if p.name not in ITS_OWN_PYTHON]


def test_no_prelude_reads_a_types_name_as_an_attribute() -> None:
    """RL-767: `type(x).__name__` (and `cls.__name__`, `__qualname__`, `__module__`) is an attribute of a class, which its
    metaclass answers; the C reads tp_name. The runtime gives the names: _tp_name, _type_name, _class_name, _type_fullname,
    _class_fullname. What is left reads an attribute because the C does (PyObject_GetAttr), or is build_class.py, which
    CPython runs for the evaluators."""
    allowed = {"build_class.py": 4, "_warnings.py": 1, "_functools.py": 1, "_typing.py": 1, "bootstrap.py": 1}
    found: dict[str, int] = {}
    for path in _preludes():
        for _number, code in _c_lines(path):
            hits = len(re.findall(r"(?<![\w.])(?:type\([^()]*\)|cls|owner|klass|kind|got|category|compute_value|method|args\[0\]|t)\.__(?:name|qualname|module)__(?!\s*=[^=])", code))
            if hits:
                found[path.name] = found.get(path.name, 0) + hits
    assert found == allowed, found


def test_no_prelude_assigns_an_errors_context() -> None:
    """RL-759: `error.__context__ = first` is an attribute assignment, which a __setattr__ of the exception's class
    takes; _PyErr_ChainExceptions1 stores the field (_set_context)."""
    found = [f"{path.name}:{number}" for path in _preludes() for number, code in _c_lines(path)
             if re.search(r"\.__(?:context|cause)__\s*=[^=]", code)]
    assert not found, found


def test_no_prelude_loops_over_an_iterator_it_took() -> None:
    """RL-765: `it = iter(x)` and then `for item in it` asks the iterator for an iterator again; the C took it once and
    calls tp_iternext (_tp_iter)."""
    found: list[str] = []
    for path in _preludes():
        taken: dict[str, int] = {}
        for number, code in _c_lines(path):
            if assigned := re.match(r"\s*([A-Za-z_][\w.]*)\s*(?::[^=]+)?=\s*(iter\()?", code):
                if assigned.group(2):
                    taken[assigned.group(1)] = number
                else:
                    taken.pop(assigned.group(1), None)   # bound to something else since
            looped = re.match(r"\s*for .+ in ([A-Za-z_][\w.]*):", code)
            if looped and looped.group(1) in taken and number - taken[looped.group(1)] < 60:
                found.append(f"{path.name}:{number}")
            if re.match(r"\s*for .+ in iter\(", code):
                found.append(f"{path.name}:{number}")
    assert not found, found


def pytest_generate_tests(metafunc: Any) -> None:
    if "finding" in metafunc.fixturenames:
        metafunc.parametrize("finding", FINDINGS, ids=[f"{rl}-{name}" for rl, name, _ in FINDINGS])


def test_finding(finding: tuple[str, str, str]) -> None:
    same(finding[2])


if __name__ == "__main__":
    test_no_prelude_reads_a_types_name_as_an_attribute()
    test_no_prelude_assigns_an_errors_context()
    test_no_prelude_loops_over_an_iterator_it_took()
    for row in FINDINGS:
        same(row[2])
        print("ok", row[0])
