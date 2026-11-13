"""Review F21 (docs/reviews/2026-11-12-fable-21-review.md; review log RL-430 to RL-444): the last commits of 2026-11-12 read
again. Each program runs compiled and under CPython on one host; what stops by name is checked compiled alone.

Run under pytest or directly: python3 -m pipeline.tests.test_review_2026_11_12
"""
from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path

from pipeline.build import build
from pipeline.tests.test_review_2026_11_03 import same

# RL-430. Every built-in a class may inherit from, every method it has: a subclass overrides the one method and asks the base for
# it. The base's own, called directly, never runs the override (it reads the object's storage), and through the override it runs
# once. bytes.__hash__ and frozenset.__hash__ went back through hash() to the override, without end.
BASES_OWN = r"""
def show(value):
    if type(value).__name__.endswith(("iterator", "_iterator", "reverseiterator")) or type(value).__name__ in ("generator", "reversed"):
        value = list(value)
    if isinstance(value, (set, frozenset)):
        return type(value).__name__ + repr(sorted(value))
    return type(value).__name__ + ":" + repr(value)

def attempt(thunk):
    try:
        return show(thunk())
    except RecursionError:
        return "RecursionError"
    except Exception as exc:
        return "raises " + type(exc).__name__

UNARY = ["__len__", "__iter__", "__hash__", "__repr__", "__str__", "__bool__", "__neg__", "__pos__", "__abs__", "__invert__", "__int__", "__float__",
         "__index__", "__reversed__", "__trunc__", "__floor__", "__ceil__", "__round__", "__complex__", "__bytes__", "__getnewargs__", "__length_hint__",
         "copy", "keys", "values", "items", "bit_length", "conjugate", "is_integer", "hex", "upper", "lower", "strip", "split", "decode", "isdigit"]
BINARY = ["__add__", "__radd__", "__sub__", "__rsub__", "__mul__", "__rmul__", "__mod__", "__rmod__", "__floordiv__", "__rfloordiv__", "__truediv__",
          "__rtruediv__", "__pow__", "__rpow__", "__divmod__", "__rdivmod__", "__and__", "__rand__", "__or__", "__ror__", "__xor__", "__rxor__",
          "__lshift__", "__rlshift__", "__rshift__", "__rrshift__", "__eq__", "__ne__", "__lt__", "__le__", "__gt__", "__ge__", "__contains__",
          "__getitem__", "__format__", "count", "index", "union", "intersection", "difference", "symmetric_difference", "issubset", "issuperset",
          "isdisjoint", "get", "startswith", "endswith", "find", "join", "__matmul__", "__iadd__", "__imul__", "__ior__", "__iand__", "__ixor__", "__isub__"]
SAMPLES = [(list, [1, 2], {"__mul__": 2, "__rmul__": 2, "__imul__": 2, "__getitem__": 0, "__contains__": 1, "count": 1, "index": 1, "__format__": ""}),
           (tuple, (1, 2), {"__mul__": 2, "__rmul__": 2, "__getitem__": 0, "__contains__": 1, "count": 1, "index": 1, "__format__": ""}),
           (str, "ab", {"__mul__": 2, "__rmul__": 2, "__getitem__": 0, "__contains__": "a", "count": "a", "index": "a", "__format__": "", "__mod__": (),
                        "startswith": "a", "endswith": "b", "find": "b", "join": ["x", "y"]}),
           (bytes, b"ab", {"__mul__": 2, "__rmul__": 2, "__getitem__": 0, "__contains__": 97, "count": b"a", "index": b"a", "__format__": "", "__mod__": (),
                           "startswith": b"a", "endswith": b"b", "find": b"b", "join": [b"x", b"y"]}),
           (bytearray, b"ab", {"__mul__": 2, "__rmul__": 2, "__imul__": 2, "__getitem__": 0, "__contains__": 97, "count": b"a", "index": b"a", "__format__": "",
                               "__mod__": (), "startswith": b"a", "endswith": b"b", "find": b"b", "join": [b"x", b"y"], "__iadd__": b"c"}),
           (set, {1, 2}, {"__contains__": 1, "__format__": ""}),
           (frozenset, {1, 2}, {"__contains__": 1, "__format__": ""}),
           (dict, {1: 2}, {"__getitem__": 1, "__contains__": 1, "get": 1, "__format__": ""}),
           (int, 5, {"__format__": "", "__pow__": 2, "__rpow__": 2, "__lshift__": 1, "__rshift__": 1, "__rlshift__": 1, "__rrshift__": 1}),
           (float, 2.5, {"__format__": "", "__pow__": 2.0, "__rpow__": 2.0}),
           (complex, 1 + 2j, {"__format__": "", "__pow__": 2, "__rpow__": 2})]

def probe(base, value, name, args):
    calls = []

    def method(self, *a):
        calls.append(name)
        if len(calls) > 4:
            raise RuntimeError("the override ran again")
        return getattr(super(Sub, self), name)(*a)
    Sub = type("Sub", (base,), {name: method})
    obj = Sub(value)
    direct = attempt(lambda: getattr(base, name)(obj, *args))
    ran_direct = len(calls)
    through = attempt(lambda: getattr(obj, name)(*args))
    return direct, ran_direct, through, len(calls) - ran_direct

for base, value, special in SAMPLES:
    for name in UNARY + BINARY:
        if not hasattr(base, name):
            continue
        if name in UNARY:
            args = ()
        elif name in special:
            args = (special[name],)
        else:
            args = (base(value),)
        if name == "__round__" or name == "split" or name == "strip" or name == "decode" or name == "hex" and base is float:
            args = ()
        print(base.__name__, name, *probe(base, value, name, args))
class HB(bytes):
    def __hash__(self): return super().__hash__()
class HF(frozenset):
    def __hash__(self): return super().__hash__()
class Odd(bytes):
    def __hash__(self): return 5
print(hash(HB(b"abc")) == hash(b"abc"), hash(HF({1, 2})) == hash(frozenset({1, 2})), bytes.__hash__(Odd(b"abc")) == hash(b"abc"), hash(Odd(b"abc")),
      {HB(b"k"): 1}[b"k"], {HF({3}): 1}[frozenset({3})], hash(HB()), hash(HF()) == hash(frozenset()))
"""

# RL-431, RL-435. The position namereplace_errors gives back is where its loop stopped, and the words of its refusals.
NAMEREPLACE = r"""
import codecs
def m(f):
    try:
        return repr(f())
    except BaseException as e:
        return type(e).__name__ + ": " + str(e)
for start, end in ((2, 1), (2, 0), (3, 1), (1, 2), (0, 3), (5, 9), (-1, 2), (1, 1), (0, 0), (-9, -9), (9, 9)):
    print(start, end, m(lambda: codecs.namereplace_errors(UnicodeEncodeError("ascii", "a\xe9c", start, end, "why"))),
          m(lambda: codecs.backslashreplace_errors(UnicodeEncodeError("ascii", "a\xe9c", start, end, "why"))),
          m(lambda: codecs.xmlcharrefreplace_errors(UnicodeEncodeError("ascii", "a\xe9c", start, end, "why"))))
print(m(lambda: codecs.namereplace_errors(UnicodeEncodeError("ascii", "", 0, 1, "why"))), m(lambda: codecs.namereplace_errors(UnicodeEncodeError("ascii", "\U000f0000͸\ud800", 0, 3, "why"))))
print(m(lambda: codecs.namereplace_errors(1)), m(lambda: codecs.namereplace_errors(UnicodeDecodeError("utf-8", b"\xff", 0, 1, "why"))),
      m(lambda: codecs.namereplace_errors(UnicodeTranslateError("a", 0, 1, "why"))), m(lambda: codecs.namereplace_errors()), m(lambda: codecs.namereplace_errors(1, 2)),
      m(lambda: codecs.namereplace_errors(exc=1)), m(lambda: b"\xff".decode("ascii", "namereplace")), m(lambda: b"\xff".decode("utf-8", "namereplace")),
      m(lambda: b"\xff\xff".decode("utf-16", "namereplace")), m(lambda: "a\xe9€".encode("ascii", "namereplace")), m(lambda: "€".encode("latin-1", "namereplace")),
      m(lambda: "\ud800".encode("utf-8", "namereplace")), m(lambda: "\ud800".encode("utf-16", "namereplace")), m(lambda: "\ud800".encode("utf-32-le", "namereplace")))
print(codecs.namereplace_errors.__name__, codecs.namereplace_errors.__doc__, type(codecs.namereplace_errors).__name__)
"""

# RL-432. The name C API is unicodedata's capsule, fetched at the handler's first use: the module is in sys.modules from then on.
# Three programs, since the first use is once in a process.
IMPORTED = [r"""
import sys
print("unicodedata" in sys.modules, "ab".encode("ascii", "namereplace"), "unicodedata" in sys.modules)
print("\xe9".encode("ascii", "namereplace"), "unicodedata" in sys.modules, type(sys.modules["unicodedata"]).__name__)
""", r"""
import codecs, sys
for wrong in (UnicodeDecodeError("utf-8", b"\xff", 0, 1, "why"), 5, UnicodeTranslateError("a", 0, 1, "why")):
    try:
        codecs.namereplace_errors(wrong)
    except TypeError:
        print("refused:", "unicodedata" in sys.modules)
try:
    b"\xff".decode("ascii", "namereplace")
except TypeError:
    print("a decoder:", "unicodedata" in sys.modules)
print(codecs.namereplace_errors(UnicodeEncodeError("ascii", "a", 1, 0, "why")), "unicodedata" in sys.modules)
""", r"""
import sys, unicodedata
kept = unicodedata._ucnhash_CAPI
def m(f):
    try:
        return repr(f())
    except BaseException as e:
        return type(e).__name__ + ": " + str(e)
unicodedata._ucnhash_CAPI = 5                    # what is no capsule is refused, and nothing is kept
print(m(lambda: "\xe9".encode("ascii", "namereplace")), m(lambda: "\ud800".encode("utf-16-le", "namereplace")))
unicodedata._ucnhash_CAPI = kept
print(m(lambda: "\xe9".encode("ascii", "namereplace")))
unicodedata._ucnhash_CAPI = 5                    # kept since the first success: not asked for again
print(m(lambda: "\xe9".encode("ascii", "namereplace")))
"""]

# RL-434. Each answer of the database is a new str, but for the empty one and one Latin-1 character.
A_NEW_STR = r"""
import unicodedata as ud
for f in (ud.category, ud.bidirectional, ud.east_asian_width, ud.block, ud.grapheme_cluster_break, ud.indic_conjunct_break, ud.decomposition, ud.name,
          ud.ucd_3_2_0.category, ud.ucd_3_2_0.bidirectional, ud.ucd_3_2_0.east_asian_width, ud.ucd_3_2_0.decomposition):
    print(f.__name__, [(f(ch), f(ch) is f(ch)) for ch in ("a", "あ", "क", "\xe9", "\U0001f1e6", "1")])
"""

# RL-433. The fields of unicodedata's iterator and segment are C struct members in CPython; here a program can write them. A value
# the C could hold is read as PyUnicode_Substring reads it; what it could not hold stops by name where the runtime would read it
# (a state the prelude's own Python cannot index raises there, an ordinary exception).
FIELDS_READ = ("import unicodedata\nseg = next(unicodedata.iter_graphemes('abc'))\nseg._c_end = 10**9\nprint(str(seg))\nseg._b_start = 1\nprint(str(seg))\n"
               "seg._b_start = 7\nprint(repr(str(seg)))\nseg._c_end = 0\nseg._b_start = 2\nprint(repr(str(seg)))\nseg._b_start = -1\n"
               "try:\n    str(seg)\nexcept IndexError as exc:\n    print(type(exc).__name__, exc)\n")
FIELDS_STOP = ["import unicodedata\nprint('start')\nit = unicodedata.iter_graphemes('abc')\nit._b_state = (0,)\nnext(it)\n",
               "import unicodedata\nprint('start')\nit = unicodedata.iter_graphemes('abc')\nit._b_state = (0, 0, 3, 0, 0, 0, 'x')\nnext(it)\n",
               "import unicodedata\nprint('start')\nit = unicodedata.iter_graphemes('abc')\nit._b_state = (0, 2, 99, 0, 0, 0, 0)\nnext(it)\n",
               "import unicodedata\nprint('start')\nit = unicodedata.iter_graphemes('abc')\nit._b_state = (0, 0, 3, 0, 9, 0, 0)\nnext(it)\n",
               "import unicodedata\nprint('start')\nit = unicodedata.iter_graphemes('abc')\nit._a_string = 5\nnext(it)\n",
               "import unicodedata\nprint('start')\nseg = next(unicodedata.iter_graphemes('abc'))\nseg._a_string = b'abc'\nstr(seg)\n",
               "import unicodedata\nprint('start')\nseg = next(unicodedata.iter_graphemes('abc'))\nseg._c_end = 'x'\nstr(seg)\n"]

# RL-437. int(), float() and complex() of a str, ASCII and beyond, give what they gave (the ASCII text is read where it is).
NUMBERS = r"""
def m(f):
    try:
        return repr(f())
    except BaseException as e:
        return type(e).__name__ + ": " + str(e)
for text in ("12", " 12 ", "1_2", "0x1f", "٣٤", "  12 　", "1\x7f٣", "", "a", "12" * 30, "٣" * 5000, "1.5", "1e3", "1+2j", "(1+2j)", "٣.٥"):
    print(ascii(text[:12]), len(text), m(lambda: int(text)), m(lambda: int(text, 0)), m(lambda: float(text)), m(lambda: complex(text)))
"""


def test_a_bases_own_method_under_a_subclass_that_overrides_it() -> None:
    same(BASES_OWN)


def test_namereplace_errors_position_and_words() -> None:
    same(NAMEREPLACE)


def test_namereplace_imports_unicodedata_at_its_first_use() -> None:
    for program in IMPORTED:
        same(program)


def test_the_database_answers_with_a_new_str() -> None:
    same(A_NEW_STR)


def _compiled(source: str) -> subprocess.CompletedProcess[str]:
    with tempfile.TemporaryDirectory() as tmp:
        prog = Path(tmp, "prog.py")
        prog.write_text(source, encoding="utf-8")
        return subprocess.run([str(build(prog, "prog.py"))], capture_output=True, text=True, check=False, cwd=tmp)


def test_fields_a_program_wrote_into_a_segment_or_an_iterator() -> None:
    if shutil.which("g++") is None:
        return
    got = _compiled(FIELDS_READ)
    assert (got.returncode, got.stdout) == (0, "abc\nbc\n''\n''\nIndexError string index out of range\n"), got
    for source in FIELDS_STOP:
        got = _compiled(source)
        assert (got.returncode, got.stdout) == (70, "start\n") and "whose fields the program changed" in got.stderr, (source, got)


def test_numbers_from_a_str() -> None:
    same(NUMBERS)


if __name__ == "__main__":
    test_a_bases_own_method_under_a_subclass_that_overrides_it()
    test_namereplace_errors_position_and_words()
    test_namereplace_imports_unicodedata_at_its_first_use()
    test_the_database_answers_with_a_new_str()
    test_fields_a_program_wrote_into_a_segment_or_an_iterator()
    test_numbers_from_a_str()
