"""Review A29 of 2026-11-21 (range 2977264..b04274c), compiled against CPython: a program for each finding fixed.

Codex's Astra at low effort read the native stack's step (RL-624, C-8-20), the sweep of a type's slots (RL-621) and the
fixes of review A28; the review log has its ten findings as RL-628 to RL-637, and RL-638 found beside them. Held here:
the special methods a prelude looked up on the class, which asks the metaclass, or called with the object where the
type's descriptor has bound them (csv's number check, RL-628; math's ceil, floor and trunc, RL-629 and RL-630;
operator.length_hint, RL-631; _locale.bindtextdomain's path, RL-635; a class statement's namespace, RL-636; Counter's
fast path and the format of a type variable's evaluator, RL-638), and the walks of nested data that the recursion
limit of Python calls ended (RL-637). The counts under a recursion limit are the sweep
pipeline/tests/test_recursion_counts.py (RL-632, RL-633); RL-634 is the harness's own
(conformance/tests/test_harness.py).

Run under pytest or directly: python3 -m pipeline.tests.test_review_2026_11_21_a29
"""
from __future__ import annotations

from typing import Any

from pipeline.tests.test_review_2026_11_19 import same

# a metaclass that answers for every special name, and the two shapes of a method a type's own lookup binds otherwise
SHAPES = r'''
asked = []
class Answers(type):
    def __getattr__(cls, name):
        if name.startswith("__") and name.endswith("__"):
            asked.append(name)
            return lambda *args: 17
        raise AttributeError(name)
class Fake(metaclass=Answers):
    def __str__(self): return "field"
def attempt(label, act):
    try: print(label, "->", repr(act()), "| the metaclass was asked for:", asked or "nothing")
    except Exception as e: print(label, "->", type(e).__name__, "| the metaclass was asked for:", asked or "nothing")
    asked.clear()
'''

FINDINGS: list[tuple[str, str, str]] = [
    ('RL-628', 'csv: a field is a number by its type, not by its metaclass', SHAPES + r'''
import csv, io
class Number:
    def __init__(self, text): self.text = text
    def __str__(self): return self.text
class Indexed(Number):
    def __index__(self): return 1
class Floating(Number):
    def __float__(self): return 1.0
class Late(Number): pass
late = Late("late")
late.__float__ = lambda: 1.0                     # in the object's own dict: no slot
for quoting in (csv.QUOTE_NONNUMERIC, csv.QUOTE_STRINGS, csv.QUOTE_NOTNULL):
    s = io.StringIO()
    csv.writer(s, quoting=quoting).writerow([Fake(), Indexed("index"), Floating("float"), late, 3, 2.5, 1j, True, "text", None])
    attempt("quoting " + str(quoting), s.getvalue)
'''),
    ('RL-629', 'math.ceil, floor and trunc: the method is the type\'s, bound by its descriptor (RL-630)', SHAPES + r'''
import math
class Static:
    __ceil__ = staticmethod(lambda: 17)
    __floor__ = staticmethod(lambda: 18)
    __trunc__ = staticmethod(lambda: 19)
class ByClass:
    @classmethod
    def __ceil__(cls): return cls.__name__
    @classmethod
    def __floor__(cls): return cls.__name__
    @classmethod
    def __trunc__(cls): return cls.__name__
class Plain:
    def __ceil__(self): return 1
    def __floor__(self): return 2
    def __trunc__(self): return 3
class NoneOf:
    __ceil__ = None
    __floor__ = None
    __trunc__ = None
class Late: pass
late = Late()
late.__ceil__ = late.__floor__ = late.__trunc__ = lambda: 5
class Real(float):
    def __ceil__(self): return "own ceil"
for f in (math.ceil, math.floor, math.trunc):
    for value in (Fake(), Static(), ByClass(), Plain(), NoneOf(), late, Real(2.5), 2.5):
        attempt(f.__name__ + " of " + type(value).__name__, lambda: f(value))
'''),
    ('RL-631', 'operator.length_hint asks nothing once it found no hint', SHAPES + r'''
import operator
class Hinted:
    def __length_hint__(self): return 7
class Static:
    __length_hint__ = staticmethod(lambda: 8)
class Late: pass
late = Late()
late.__length_hint__ = lambda: 9
for value in (Fake(), Hinted(), Static(), late, [1, 2], iter([1, 2, 3]), object()):
    attempt("length_hint of " + type(value).__name__, lambda: operator.length_hint(value, 23))
'''),
    ('RL-635', '_locale.bindtextdomain converts its path as os.fspath does', SHAPES + r'''
import _locale
class Static:
    __fspath__ = staticmethod(lambda: "/tmp")
class Plain:
    def __fspath__(self): return "/tmp"
class Wrong:
    def __fspath__(self): return 3
class Late: pass
late = Late()
late.__fspath__ = lambda: "/tmp"
for value in (Fake(), Static(), Plain(), Wrong(), late, "/tmp", b"/tmp", None):
    attempt("bindtextdomain with " + type(value).__name__, lambda: _locale.bindtextdomain("bella-a29-example", value))
'''),
    ('RL-636', 'what __prepare__ returns is a mapping by its type\'s slot', SHAPES + r'''
class NoCall:
    __getitem__ = None
class Late: pass
late = Late()
late.__getitem__ = lambda key: 1
class Real(dict): pass
for label, namespace in (("the metaclass answers", Fake()), ("__getitem__ = None", NoCall()), ("in the object's own dict", late), ("a dict subclass", Real())):
    class Make(type):
        @classmethod
        def __prepare__(cls, name, bases, namespace=namespace): return namespace
    def build():
        class T(metaclass=Make): pass
        return type(T).__name__
    attempt(label, build)
'''),
    ('RL-637', 'a walk of nested data is not a recursion of Python calls', r'''
import collections, functools, json, sys, types
def nested(make, depth=100):
    x = make(0)
    for _ in range(depth): x = make(x)
    return x
kinds = {"list": lambda v: [v], "tuple": lambda v: (v,), "dict": lambda v: {"k": v}, "deque": lambda v: collections.deque([v]),
         "OrderedDict": lambda v: collections.OrderedDict(k=v), "defaultdict": lambda v: collections.defaultdict(int, k=v),
         "frozenset": lambda v: frozenset([v]), "SimpleNamespace": lambda v: types.SimpleNamespace(k=v),
         "partial": lambda v: functools.partial(print, v)}
walks = {"repr": repr, "str": str, "format": lambda v: format(v), "f-string": lambda v: f"{v}", "percent r": lambda v: "%r" % (v,),
         "ascii": ascii, "eq": lambda v: v == other, "ne": lambda v: v != other, "in a list": lambda v: v in [other],
         "index": lambda v: [other].index(v), "count": lambda v: [other].count(v)}
for kind, make in kinds.items():
    value, other = nested(make), nested(make)
    sys.setrecursionlimit(50)
    row = []
    for name, walk in walks.items():
        try:
            walk(value)
            row.append(name)
        except RecursionError:
            row.append(name + ": RecursionError")
    sys.setrecursionlimit(1000)
    print(kind, "|", ", ".join(row))
value = nested(lambda v: [v])
sys.setrecursionlimit(50)
try: print("json.dumps:", len(json.dumps(value)))
except RecursionError: print("json.dumps: RecursionError")
sys.setrecursionlimit(1000)
print("and a Python function still meets the limit:", end=" ")
def down(n): return down(n + 1)
try: down(0)
except RecursionError: print("RecursionError")
'''),
    ('RL-638', 'Counter\'s fast path and a type variable\'s format are decided by the type', r'''
import collections, typing
class Raises(type):
    @property
    def get(cls): raise ValueError("the metaclass was asked for get")
    @property
    def __setitem__(cls): raise ValueError("the metaclass was asked for __setitem__")
class Counted(collections.Counter, metaclass=Raises): pass
try: print(sorted(Counted("abracadabra").items()))
except ValueError as e: print("ValueError", e.args)
class Format:
    def __index__(self): return 1                # VALUE
shadowed = Format()
shadowed.__index__ = lambda: 4                   # STRING, in the object's own dict: not what the C reads
T = typing.TypeVar("T", bound=int)
for label, fmt in (("the type's __index__", Format()), ("the object's own", shadowed), ("1", 1), ("4", 4)):
    try: print(label, "->", repr(T.evaluate_bound(fmt)))
    except Exception as e: print(label, "->", type(e).__name__)
class Late: pass
late = Late()
late.__index__ = lambda: 1
try: print(T.evaluate_bound(late))
except TypeError: print("no slot -> TypeError")
'''),
]


def pytest_generate_tests(metafunc: Any) -> None:
    if "finding" in metafunc.fixturenames:
        metafunc.parametrize("finding", FINDINGS, ids=[f"{rl}-{name}" for rl, name, _ in FINDINGS])


def test_finding(finding: tuple[str, str, str]) -> None:
    same(finding[2])


if __name__ == "__main__":
    for row in FINDINGS:
        same(row[2])
        print("ok", row[0])
