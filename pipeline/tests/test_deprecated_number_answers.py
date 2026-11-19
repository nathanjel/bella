"""The number methods' deprecated answers, compiled against CPython (C-6-23).

An `__index__`, `__int__`, `__float__` or `__complex__` that answers with an instance of a strict subclass is taken with a
DeprecationWarning (Objects/abstract.c: _PyNumber_Index, PyNumber_Long, PyNumber_Float; floatobject.c: PyFloat_AsDouble;
complexobject.c: try_complex_special_method), and so is a complex number given to complex() as a part. Until 2026-11-19
the runtime stopped by name at each. The warning is raised where the runtime converts, so every place that takes a number
gets it; the case has one row for each of CPython's functions, and here is a sweep of the places a program reaches them
from: the built-in types' methods, the builtins, and the modules whose C takes a number (math, cmath, struct, operator,
itertools, time, os, random's seed). A place that the struct prelude had converted by hand gave no warning (found by the
case), which is why the sweep is wide.

Run under pytest or directly: python3 -m pipeline.tests.test_deprecated_number_answers
"""
from __future__ import annotations

from pipeline.tests.test_compiled_imports import same

SWEEP = r"""
import cmath
import itertools
import math
import operator
import os
import struct
import warnings


class Wide(int):
    pass


class Long(float):
    pass


class Pair(complex):
    pass


class Index:
    def __init__(self, value=3):
        self.value = value

    def __index__(self):
        return Wide(self.value)


class Int:
    def __int__(self):
        return Wide(7)


class Bool:
    def __index__(self):
        return True

    def __int__(self):
        return False


class Float:
    def __init__(self, value=2.25):
        self.value = value

    def __float__(self):
        return Long(self.value)


class Complex:
    def __complex__(self):
        return Pair(1, 2)


class Both:                                       # __int__ is asked before __index__ by int(), __float__ before __index__ by float()
    def __int__(self):
        return Wide(1)

    def __index__(self):
        return Wide(2)

    def __float__(self):
        return Long(3.0)


class NotOne:                                     # not an int, a float or a complex at all: a TypeError, no warning
    def __index__(self):
        return 1.5

    def __int__(self):
        return "7"

    def __float__(self):
        return 2

    def __complex__(self):
        return 1.0


seq = [10, 20, 30, 40, 50, 60]
text = "abcdefgh"
octets = b"abcdefgh"

SITES = {
    # __index__
    "list[i]": lambda: seq[Index()],
    "list[i:j:k]": lambda: seq[Index(1):Index(5):Index(2)],
    "str[i]": lambda: text[Index()],
    "bytes[i]": lambda: octets[Index()],
    "tuple[i]": lambda: tuple(seq)[Index()],
    "bytearray[i]": lambda: bytearray(octets)[Index()],
    "range[i]": lambda: range(10)[Index()],
    "list[i] = v": lambda: [seq.copy() for _ in range(1)][0].__setitem__(Index(), 0),
    "del list[i]": lambda: [seq.copy() for _ in range(1)][0].__delitem__(Index()),
    "list * i": lambda: [1] * Index(),
    "i * list": lambda: Index() * [1],
    "str * i": lambda: "ab" * Index(),
    "bytes * i": lambda: b"ab" * Index(),
    "tuple * i": lambda: (1,) * Index(),
    "list.insert": lambda: (lambda made: (made.insert(Index(), "x"), made)[1])(seq.copy()),
    "list.pop": lambda: seq.copy().pop(Index()),
    "list.index start": lambda: seq.index(50, Index()),
    "str.center": lambda: "x".center(Index()),
    "str.ljust": lambda: "x".ljust(Index()),
    "str.zfill": lambda: "x".zfill(Index()),
    "str.expandtabs": lambda: "a\tb".expandtabs(Index()),
    "str.split maxsplit": lambda: "a b c d e".split(None, Index(2)),
    "str.find start": lambda: text.find("e", Index()),
    "str.count end": lambda: text.count("a", 0, Index()),
    "bytes(n)": lambda: bytes(Index()),
    "bytearray(n)": lambda: bytearray(Index()),
    "bytes([i])": lambda: bytes([Index(65)]),
    "bytearray.append": lambda: (lambda made: (made.append(Index(65)), made)[1])(bytearray()),
    "bytes.hex bytes_per_sep": lambda: octets.hex(":", Index(2)),
    "int.to_bytes": lambda: (1).to_bytes(Index(), "big"),
    "int(text, base)": lambda: int("12", Index()),
    "int << i": lambda: 1 << Index(),
    "range(i)": lambda: range(Index()),
    "range(i, j, k)": lambda: list(range(Index(0), Index(9), Index(3))),
    "slice.indices": lambda: slice(None).indices(Index()),
    "chr": lambda: chr(Index(65)),
    "bin": lambda: bin(Index()),
    "hex": lambda: hex(Index()),
    "oct": lambda: oct(Index()),
    "round digits": lambda: round(1.23456, Index()),
    "round int digits": lambda: round(12345, Index(-2)),
    "enumerate start": lambda: list(enumerate("ab", Index())),
    "pow mod": lambda: pow(2, 5, 7) + operator.index(Index()),
    "%x": lambda: "%x" % Index(255),
    "%c": lambda: "%c" % Index(65),
    "%*d": lambda: "%*d" % (Index(), 5),
    "format spec via int": lambda: format(operator.index(Index()), "03d"),
    "operator.index": lambda: operator.index(Index()),
    "operator.index bool": lambda: operator.index(Bool()),
    "math.factorial": lambda: math.factorial(Index()),
    "math.comb": lambda: math.comb(Index(5), Index(2)),
    "math.perm": lambda: math.perm(Index(5), Index(2)),
    "math.gcd": lambda: math.gcd(Index(12), Index(18)),
    "math.isqrt": lambda: math.isqrt(Index(17)),
    "math.ldexp": lambda: math.ldexp(1.0, Index()),
    "itertools.islice": lambda: list(itertools.islice(range(10), Index())),
    "itertools.repeat": lambda: list(itertools.repeat("x", Index())),
    "itertools.combinations": lambda: len(list(itertools.combinations(range(4), Index(2)))),
    "itertools.count": lambda: next(itertools.count(Index())),
    "struct i": lambda: struct.pack("<i", Index()),
    "struct q": lambda: struct.pack("<q", Index()),
    "struct B": lambda: struct.pack("<B", Index()),
    "os.urandom": lambda: len(os.urandom(Index())),
    "os.strerror": lambda: type(os.strerror(Index(2))).__name__,
    "int()": lambda: int(Index()),
    "float()": lambda: float(Index()),
    "complex()": lambda: complex(Index()),
    "math.sqrt of an index": lambda: math.sqrt(Index(9)),
    # __int__
    "int(Int)": lambda: int(Int()),
    "int(Bool)": lambda: int(Bool()),
    "%d": lambda: "%d" % Int(),
    "%i": lambda: "%i" % Int(),
    "%5d": lambda: "%5d" % Int(),
    "int(Both)": lambda: int(Both()),
    "float(Both)": lambda: float(Both()),
    "operator.index(Both)": lambda: operator.index(Both()),
    # __float__
    "float(Float)": lambda: float(Float()),
    "math.sqrt": lambda: math.sqrt(Float()),
    "math.floor": lambda: math.floor(Float()),
    "math.ceil": lambda: math.ceil(Float()),
    "math.isnan": lambda: math.isnan(Float()),
    "math.pow": lambda: math.pow(Float(), Float(2.0)),
    "math.hypot": lambda: math.hypot(Float(3.0), Float(4.0)),
    "math.fsum": lambda: math.fsum([Float(), Float()]),
    "math.copysign": lambda: math.copysign(Float(), -1.0),
    "math.atan2": lambda: math.atan2(Float(0.0), Float(1.0)),
    "math.frexp": lambda: math.frexp(Float(8.0)),
    "math.fmod": lambda: math.fmod(Float(), 2.0),
    "math.dist": lambda: math.dist([Float(0.0)], [Float(3.0)]),
    "math.prod start": lambda: math.prod([2.0], start=float(Float())),
    "%f": lambda: "%f" % Float(),
    "%e": lambda: "%e" % Float(),
    "%g": lambda: "%g" % Float(),
    "complex(Float)": lambda: complex(Float()),
    "complex(Float, Float)": lambda: complex(Float(), Float()),
    "cmath.sqrt(Float)": lambda: cmath.sqrt(Float(4.0)),
    "cmath.phase(Float)": lambda: cmath.phase(Float()),
    "cmath.rect": lambda: cmath.rect(Float(1.0), Float(0.0)),
    "struct d": lambda: struct.pack("<d", Float()),
    "struct f": lambda: struct.pack("<f", Float()),
    "struct e": lambda: struct.pack("<e", Float()),
    "float.fromhex no": lambda: float.fromhex("0x1p0") + float(Float()),
    # __complex__
    "complex(Complex)": lambda: complex(Complex()),
    "complex(Complex, 1)": lambda: complex(Complex(), 1),
    "complex(Complex, Float)": lambda: complex(Complex(), Float()),
    "cmath.sqrt": lambda: cmath.sqrt(Complex()),
    "cmath.exp": lambda: cmath.exp(Complex()),
    "cmath.polar": lambda: cmath.polar(Complex()),
    "cmath.isfinite": lambda: cmath.isfinite(Complex()),
    "cmath.isclose": lambda: cmath.isclose(Complex(), Complex()),
    "struct D": lambda: struct.pack("<D", Complex()),
    "struct F": lambda: struct.pack("<F", Complex()),
    # a complex part
    "complex(1j, 2)": lambda: complex(1j, 2),
    "complex(1, 2j)": lambda: complex(1, 2j),
    "complex(1j, 2j)": lambda: complex(1j, 2j),
    "complex(real=1j)": lambda: complex(real=1j),
    "complex(imag=1j)": lambda: complex(imag=1j),
    "complex(1j, imag=2)": lambda: complex(1j, imag=2),
    "complex(Pair, 1)": lambda: complex(Pair(1, 2), 1),
    "complex(1, Pair)": lambda: complex(1, Pair(1, 2)),
    "complex(Pair, Pair)": lambda: complex(Pair(1, 2), Pair(3, 4)),
    "Pair(1j, 2j)": lambda: Pair(1j, 2j),
    "complex(1j, Float)": lambda: complex(1j, Float()),
    "complex(Float, 1j)": lambda: complex(Float(), 1j),
    "complex(Index, 1j)": lambda: complex(Index(), 1j),
    "complex(-0.0, 0j)": lambda: complex(-0.0, 0j),
    "complex(0j, -0.0)": lambda: complex(0j, -0.0),
    "complex(inf*1j, 1j)": lambda: complex(complex(0.0, float("inf")), 1j),
    # what answers with another type altogether
    "operator.index(NotOne)": lambda: operator.index(NotOne()),
    "int(NotOne)": lambda: int(NotOne()),
    "float(NotOne)": lambda: float(NotOne()),
    "complex(NotOne)": lambda: complex(NotOne()),
    "math.sqrt(NotOne)": lambda: math.sqrt(NotOne()),
    # no warning: the subclass's instance itself is the argument
    "int(Wide)": lambda: (int(Wide(3)), type(int(Wide(3))).__name__),
    "float(Long)": lambda: (float(Long(1.5)), type(float(Long(1.5))).__name__),
    "complex(Pair)": lambda: (complex(Pair(1, 2)), type(complex(Pair(1, 2))).__name__),
    "list[Wide]": lambda: seq[Wide(2)],
    "list[True]": lambda: seq[True],
}


def shown(value):
    return f"{type(value).__name__} {value!r}"


for label, work in SITES.items():
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        try:
            out = shown(work())
        except Exception as exc:
            out = "raised " + type(exc).__name__
    print(label, "->", out)
    for w in caught:
        print("   ", w.category.__name__, w.lineno, w.filename == __file__, w.message)
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        try:
            out = shown(work())
        except Exception as exc:
            out = "raised " + type(exc).__name__ + (" " + type(exc.__context__).__name__ if exc.__context__ is not None else "")
    print("    as an error:", out)

# once for a place with the filters a program starts with, and the registry it is counted in
def place():
    return int(Int())


for turn in range(3):
    place()
print(sorted(key[0][:30] for key in __warningregistry__ if isinstance(key, tuple)))
"""


def test_every_place_that_takes_a_number() -> None:
    same({"main.py": SWEEP}, stderr=True)


if __name__ == "__main__":
    for name, value in sorted(globals().items()):
        if name.startswith("test_") and callable(value):
            value()
    print("ok")
