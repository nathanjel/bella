"""Reviews A15 (Codex 6.1-sol, high) and G15 (gemini-argon-4, medium) of 2026-11-09, RL-369 to RL-393: every confirmed finding's
program and what stands around it, compiled, against CPython. The 4 GiB zlib input (RL-369) runs only where the machine has the
memory for it twice; the staging and eval2 findings (RL-373, RL-390) run their pipelines directly."""
from __future__ import annotations

import os
import tempfile
from pathlib import Path

from pipeline.l1.frontend import lower
from pipeline.l2 import eval2
from pipeline.l2.lifetimes import lifetimes
from pipeline.l2.lower import to_l2
from pipeline.staging.annotations import evaluators_for_source
from pipeline.tests.test_review_2026_11_03 import same

VIEW_SLOTS = r"""
class Other:
    def __iter__(self): return iter([2])
    def __ror__(self, other): return 99
print({1: 0}.keys() | Other())
try:
    print({'a': []}.items() ^ {'a': []}.items())
except TypeError as e:
    print(type(e).__name__, str(e))
for m in ("__and__", "__rand__", "__sub__", "__xor__"):
    try:
        getattr({}.keys(), m)(x=1)
    except TypeError as e:
        print(m, "->", e)
print({1} .__and__.__name__, {1}.__rsub__(x=1) if False else 'ok')
class Other2:
    def __iter__(self): return iter([5])
    def __rand__(self, other): return 'rand'
print({1: 0}.keys() & Other2(), [1] | {2: 0}.keys(), {1: 0}.items() ^ {1: 1}.items(), {1: 0}.keys() - {1}, {2} - {1: 0, 2: 0}.keys())
for m in ('__and__', '__rand__', '__sub__', '__rsub__', '__xor__', '__rxor__', '__or__', '__ror__'):
    try:
        getattr({1}, m)(x=1)
    except TypeError as e:
        print(m, e)

"""

EXCEPTHOOK = r"""
import io, sys
try:
    1 / 0
except ZeroDivisionError as e:
    tb = e.__traceback__
sys.stderr = io.StringIO()
sys.excepthook(ValueError, ValueError('new'), tb)
print('Traceback' in sys.stderr.getvalue())
"""

WARNINGS_REGISTRY_AND_LINES = r"""
import warnings
for val in (None, 123):
    with warnings.catch_warnings(record=True) as r:
        warnings.simplefilter("always")
        globals()["__warningregistry__"] = val
        try:
            warnings.warn("hello")
            print(val, "ok", len(r))
        except Exception as e:
            print(val, type(e).__name__, e)
with warnings.catch_warnings(record=True) as w:
    warnings.simplefilter("always")
    x = [
        1 +
        (warnings.warn("in comp") or 0)
        for _ in range(1)
    ]
    print("lineno:", w[0].lineno)
with warnings.catch_warnings(record=True) as w:
    warnings.simplefilter("always")
    x = (
        1 +
        (warnings.warn("plain") or 0)
    )
    y = [
        warnings.warn("comp")
        for _ in range(1)
    ]
    z = [
        1 +
        (warnings.warn("deep") or 0)
        for _ in range(1)
    ]
    print([m.lineno for m in w])

try:
    x = (
        1 +
        (1 / 0)
    )
except ZeroDivisionError as e:
    print(e.__traceback__.tb_lineno)
try:
    y = [
        1 +
        (1 / 0)
        for _ in range(1)
    ]
except ZeroDivisionError as e:
    print(e.__traceback__.tb_lineno)

"""

TOKENIZE_ARGS = r"""
import _tokenize
class BadBool:
    def __bool__(self):
        raise RuntimeError("bad bool")
for kw in [
    {"extra_tokens": BadBool(), "encoding": 123},
    {"extra_tokens": 1, "encodin": "utf-8"},
]:
    try:
        _tokenize.TokenizerIter(lambda: "", **kw)
    except Exception as e:
        print(type(e).__name__, e)
"""

ZLIB_ZDICT = r"""
import zlib
zd = bytearray(b"hello world")
co = zlib.compressobj(zdict=zd)
stream = co.compress(b"hello world hello world") + co.flush()
do = zlib.decompressobj(zdict=zd)
zd[:] = b"wrong dict!"
try:
    print(repr(do.decompress(stream)))
except Exception as e:
    print(type(e).__name__, e)
zd2 = bytearray(b'hello world')
co = zlib.compressobj(zdict=zd2)
stream = co.compress(b'hello world hello world') + co.flush()
do = zlib.decompressobj(zdict=zd2)
print(do.decompress(stream))
zd2[:] = b'changed now!'
print(do.decompress(b''))
try:
    zlib.decompressobj(zdict=3)
except TypeError as e:
    print(e)
raw = zlib.compressobj(wbits=-15, zdict=b'dict')
data = raw.compress(b'dict dict') + raw.flush()
print(zlib.decompressobj(wbits=-15, zdict=b'dict').decompress(data))

"""

TIME_WDAY = r"""
import time
for fn in [
    lambda: time.asctime((2024, 1, 1, 0, 0, 0, -2, 1, 0)),
    lambda: time.strftime("%a", (2024, 1, 1, 0, 0, 0, -2, 1, 0)),
]:
    try:
        print("OK", repr(fn()))
    except Exception as e:
        print(type(e).__name__, e)
print(time.asctime((2024, 1, 1, 0, 0, 0, -1, 1, 0)), time.strftime('%a', (2024, 1, 1, 0, 0, 0, 6, 1, 0)))

"""

INDEX_HELPERS = r"""
import binascii, struct, time, math, _sha3, _blake2

class BadIdx:
    def __index__(self): return "abc"

class IdxNone:
    __index__ = None

for obj in (BadIdx(), IdxNone()):
    for name, fn in [
        ("binascii", lambda: binascii.crc32(b"a", obj)),
        ("struct", lambda: struct.pack("i", obj)),
        ("time", lambda: time.gmtime(obj)),
        ("math", lambda: math.gcd(obj, 2)),
        ("_sha3", lambda: _sha3.shake_128(b"a").digest(obj)),
        ("_blake2", lambda: _blake2.blake2b(b"a", digest_size=obj)),
    ]:
        try:
            fn()
        except Exception as e:
            print(f"{type(obj).__name__} {name}: {type(e).__name__}: {e}")
"""

AS_DOUBLE = r"""
import math, time, _statistics

class BadFloat:
    def __float__(self): return "abc"

class FloatNoneWithIndex:
    __float__ = None
    def __index__(self): return 1

class SpecialNone:
    __float__ = None
    __trunc__ = None
    __ceil__ = None
    __floor__ = None

for label, fn in [
    ("math.sin(BadFloat)", lambda: math.sin(BadFloat())),
    ("time.sleep(BadFloat)", lambda: time.sleep(BadFloat())),
    ("_statistics(BadFloat)", lambda: _statistics._normal_dist_inv_cdf(0.5, BadFloat(), 1.0)),
    ("math.sin(FloatNoneWithIndex)", lambda: math.sin(FloatNoneWithIndex())),
    ("_statistics(FloatNoneWithIndex)", lambda: _statistics._normal_dist_inv_cdf(0.5, FloatNoneWithIndex(), 1.0)),
    ("math.trunc(SpecialNone)", lambda: math.trunc(SpecialNone())),
    ("math.ceil(SpecialNone)", lambda: math.ceil(SpecialNone())),
    ("math.floor(SpecialNone)", lambda: math.floor(SpecialNone())),
]:
    try:
        print(label, "-> OK", fn())
    except Exception as e:
        print(label, "->", type(e).__name__, e)
"""

BISECT_MAPPINGS = r"""
import _bisect, _contextvars

class dict:
    def __len__(self): return 0
    def __getitem__(self, i): return i

for obj in (_contextvars.Context(), dict()):
    try:
        print("OK", _bisect.bisect_left(obj, 1))
    except Exception as e:
        print(type(e).__name__, e)
import bisect
class D(__builtins__.dict if hasattr(__builtins__, 'dict') else type({})): pass
print(_bisect.bisect_left(D(), 1), bisect.bisect_right([1, 2, 2, 3], 2), bisect.insort([1, 3], 2) or 'inserted')
try:
    _bisect.bisect_left({}, 1)
except TypeError as e:
    print(e)

"""

STR_SUBCLASS_READS = r"""
import _csv, struct, time

class MyStr(str):
    def __str__(self): return "i"
    def __iter__(self): raise RuntimeError("MyStr.__iter__")

print("csv delim:", repr(_csv.Dialect(delimiter=MyStr(";")).delimiter))
try:
    print("csv reader:", list(_csv.reader([MyStr("a,b")])))
except Exception as e:
    print("csv reader:", type(e).__name__, e)
print("struct calcsize:", struct.calcsize(MyStr("b")))
print("strftime:", repr(time.strftime(MyStr("%Y"), (2024, 1, 2, 3, 4, 5, 1, 2, 0))))
"""

RANDOM_SETSTATE = r"""
import _random
class SubTuple(tuple):
    def __getitem__(self, i):
        raise RuntimeError("SubTuple.__getitem__")
st = SubTuple(_random.Random(1).getstate())
try:
    _random.Random().setstate(st)
    print("OK")
except Exception as e:
    print(type(e).__name__, e)
try:
    _random.Random().setstate(('x',) * 625)
except Exception as e:
    print(type(e).__name__, e)

"""

UNPACK_KEYWORDS = r"""
import _csv, _contextvars, _bisect, _opcode, _md5, _blake2, _hmac, math, _thread

class BadBool:
    def __bool__(self): raise RuntimeError("bad bool")

for label, fn in [
    ("csv.get_dialect", lambda: _csv.get_dialect(a=1, b=2)),
    ("ContextVar", lambda: _contextvars.ContextVar("v", default=1, extra=2)),
    ("bisect_left", lambda: _bisect.bisect_left(a=[], x=1, lo=0, hi=0, key=None, extra=1)),
    ("opcode.is_valid", lambda: _opcode.is_valid(op=1, extra=2)),
    ("hmac.new(bad=1)", lambda: _hmac.new(bad=1)),
    ("math.isclose(bad=1)", lambda: math.isclose(bad=1)),
    ("start_joinable(bad=1)", lambda: _thread.start_joinable_thread(bad=1)),
    ("md5(dup+bad)", lambda: _md5.md5(b"a", bad=1, data=b"b")),
    ("md5(bool+bad)", lambda: _md5.md5(usedforsecurity=BadBool(), bad=1)),
    ("md5(dat=)", lambda: _md5.md5(dat=b"a")),
    ("blake2b(dat=)", lambda: _blake2.blake2b(dat=b"a")),
    ("lock.acquire(blockin=)", lambda: _thread.lock().acquire(blockin=True)),
]:
    try:
        fn()
    except Exception as e:
        print(f"{label}: {type(e).__name__}: {e}")
def f(data, *, blocking=True):
    pass
for kw in ({"dat": 1}, {"blockin": 1}, {"x": 1}):
    try:
        f(**kw)
    except TypeError as e:
        print(e)
try:
    print(len(x=1))
except TypeError as e:
    print(e)
try:
    print(int("1", bas=2))
except TypeError as e:
    print(e)

import zlib, _tokenize
for label, fn in [('compress()', lambda: zlib.compress()), ('compress(b,1,2,3)', lambda: zlib.compress(b'', 1, 2, 3)), ('compress(b, levl=1)', lambda: zlib.compress(b'', levl=1)), ('co.compress()', lambda: zlib.compressobj().compress()), ('do.decompress(b, 1, 2)', lambda: zlib.decompressobj().decompress(b'', 1, 2)), ('tokenizeriter(1,2)', lambda: _tokenize.TokenizerIter(1, 2)), ('tokenizeriter(f, encodin=)', lambda: _tokenize.TokenizerIter(lambda: '', extra_tokens=1, encodin='utf-8')), ('field_size_limit(new_limi=1)', lambda: _csv.field_size_limit(new_limi=1)), ('Dialect(delimter=)', lambda: _csv.Dialect(delimter=';')), ('ContextVar(v, defaul=1)', lambda: _contextvars.ContextVar('v', defaul=1)), ('sha3(b, bad=1, data=b)', lambda: __import__('_sha3').sha3_224(b'a', bad=1, data=b'b')), ('acquire(a=1,b=2,c=3)', lambda: _thread.lock().acquire(a=1, b=2, c=3)), ('compute_digest(b)', lambda: _hmac.compute_digest(b'k'))]:
    try:
        fn()
    except Exception as e:
        print(f'{label}: {type(e).__name__}: {e}')

"""

FORMAT_PARAMETER = r"""
type Alias = int
def f[T: int = str](x: T) -> T:
    return x

for fn in (Alias.evaluate_value, f.__type_params__[0].evaluate_bound, f.__type_params__[0].evaluate_default):
    print(fn.__code__.co_varnames)
    try:
        fn(format=1)
    except TypeError as e:
        print(e)
def outer():
    format = int
    def f(x: format): pass
    return f.__annotations__
print(outer())
def f2(x: [(a := y) for y in (1,)], w: [(format := y) for y in (2,)]): pass
print(f2.__annotations__)

"""

WALRUS_THROUGH_ANNOTATION = r"""
def f(x: [(t := y) for y in (42,)]):
    pass
print("annotations:", f.__annotations__)
print("module t:", globals().get("t", "MISSING"))

def outer():
    def g(x: [(u := y) for y in (99,)]):
        pass
    _ = g.__annotations__
    print("g.__annotate__ varnames/freevars:", g.__annotate__.__code__.co_varnames, g.__annotate__.__code__.co_freevars)
    try:
        return u
    except NameError as e:
        return f"NameError: {e}"
print("outer u:", outer())
"""


def test_dict_view_slots_order_and_names() -> None:
    """RL-370, RL-371, RL-387: the views' algebra as a number slot (the view's answer before a reflected method), items ^ items
    without hashing the pairs that cancel, and every slot wrapper named after itself."""
    same(VIEW_SLOTS)


def test_excepthook_takes_its_traceback() -> None:
    """RL-372: a traceback given for a value that has none becomes the value's."""
    same(EXCEPTHOOK)


def test_warnings_registry_and_lines() -> None:
    """RL-374, RL-375, RL-392: a module's __warningregistry__ that is not a dict, and the line a warning or a traceback is charged
    to inside a multi-line statement, with and without an inlined comprehension."""
    same(WARNINGS_REGISTRY_AND_LINES)


def test_tokenizer_arguments() -> None:
    """RL-376: TokenizerIter converts after parsing, in parameter order, and suggests a keyword."""
    same(TOKENIZE_ARGS)


def test_zlib_zdict_read_when_asked() -> None:
    """RL-377: decompressobj keeps its zdict and reads it when the stream asks; a raw stream reads it at once."""
    same(ZLIB_ZDICT)


def test_time_weekday_remainder() -> None:
    """RL-378: tm_wday below -1 is out of range, as C's remainder leaves it negative."""
    same(TIME_WDAY)


def test_index_through_the_runtime() -> None:
    """RL-379: __index__ returning a non-int and __index__ = None, with PyNumber_Index's messages, in seven modules."""
    same(INDEX_HELPERS)


def test_as_double_through_the_runtime() -> None:
    """RL-380: __float__ returning a non-float and None where a special method is looked up."""
    same(AS_DOUBLE)


def test_bisect_mapping_types() -> None:
    """RL-381: _contextvars.Context is not a sequence; a class of the program's named dict is."""
    same(BISECT_MAPPINGS)


def test_str_subclasses_read_as_text() -> None:
    """RL-383: _csv, _struct and time read a str subclass's text, not its __str__ or __iter__."""
    same(STR_SUBCLASS_READS)


def test_random_setstate_reads_the_tuple() -> None:
    """RL-384: a tuple subclass's __getitem__ is not consulted."""
    same(RANDOM_SETSTATE)


def test_unpack_keywords() -> None:
    """RL-385, RL-391: _PyArg_UnpackKeywords' messages and order through one primitive, and ceval's keyword suggestion."""
    same(UNPACK_KEYWORDS)


def test_format_parameter_names() -> None:
    """RL-389, RL-390: the PEP 695 functions keep .format; an annotate function's format beside a free or cell variable format."""
    same(FORMAT_PARAMETER)


def test_walrus_through_an_annotation_scope() -> None:
    """RL-393: a comprehension's walrus inside an annotation binds in the module or the function around the annotation."""
    same(WALRUS_THROUGH_ANNOTATION)


def test_staged_strings_keep_the_star() -> None:
    """RL-373: a PEP 563 vararg annotation *Ts is the string '*Ts'."""
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp, "m.py")
        path.write_text("from __future__ import annotations\ndef g(x: int, *args: *Ts) -> str:\n    return 'ok'\n", encoding="utf-8")
        evaluators, declined = evaluators_for_source(str(path))
    assert len(evaluators) == 1 and declined == [], declined


def test_eval2_format_beside_a_free_or_cell_variable() -> None:
    """RL-390: eval2 runs an annotate function whose code has a free or cell variable named format."""
    for src in ("def outer():\n    format = int\n    def f(x: format): pass\n    return f.__annotations__\nprint(outer())\n",
                "def f(x: [(a := y) for y in (1,)], w: [(format := y) for y in (2,)]): pass\nprint(f.__annotations__)\n"):
        eval2.Interpreter().run_module(lifetimes(to_l2(lower(src, "<test>"))))


def test_zlib_past_four_gigabytes() -> None:
    """RL-369: adler32, crc32 and compress of 2^32 bytes, where the machine can hold the input twice over."""
    pages, page = os.sysconf("SC_PHYS_PAGES"), os.sysconf("SC_PAGE_SIZE")
    if pages * page < 24 * 2**30:
        return
    same("import zlib\nx = b'x' * 2**32\nprint(zlib.adler32(x), zlib.crc32(x))\nprint(len(zlib.compress(x)))\n")
