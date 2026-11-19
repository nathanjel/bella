# clause: C-6-23
# spec: section 6 (int, float, complex), section 7 (warnings)
# status: P1
# source: Objects/abstract.c (_PyNumber_Index, PyNumber_Long, PyNumber_Float), Objects/floatobject.c (PyFloat_AsDouble),
#         Objects/complexobject.c (try_complex_special_method, complex_new_impl), review of the runtime's stops 2026-11-13
"""What CPython still takes with a DeprecationWarning where a number is asked for: an `__index__`, `__int__`, `__float__`
or `__complex__` that answers with an instance of a strict subclass of the type it should give (a bool for an int too),
and a complex number given to complex() as its real or its imaginary part. The value is taken, as a plain int, float or
complex; the warning names the class and what it answered, at the line that asked. Under a filter that makes the warning
an error the conversion fails with it, after the method was called, and struct reports its own error in its place. With
the filters a program starts with the warning is printed once for a line."""
# ruff: noqa: UP018, UP031  # the calls of complex() and the % formats are what the rows are about
import cmath
import io
import math
import operator
import os
import struct
import sys
import warnings
from collections.abc import Callable

called: list[str] = []


class Wide(int):
    pass


class Long(float):
    pass


class Pair(complex):
    pass


class GivesIndex:
    def __index__(self) -> int:
        called.append("__index__")
        return Wide(3)


class GivesInt:
    def __int__(self) -> int:
        called.append("__int__")
        return Wide(7)


class GivesBool:
    def __index__(self) -> int:
        called.append("__index__")
        return True

    def __int__(self) -> int:
        called.append("__int__")
        return True


class GivesFloat:
    def __float__(self) -> float:
        called.append("__float__")
        return Long(2.25)


class GivesComplex:
    def __complex__(self) -> complex:
        called.append("__complex__")
        return Pair(1, 2)


class IntThatGives(int):
    def __index__(self) -> int:
        called.append("__index__")
        return Wide(5)

    def __int__(self) -> int:
        called.append("__int__")
        return Wide(6)


class FloatThatGives(float):
    def __float__(self) -> float:
        called.append("__float__")
        return Long(4.5)


ROWS: list[tuple[str, Callable[[], object]]] = [
    ("operator.index", lambda: operator.index(GivesIndex())),
    ("operator.index, a bool", lambda: operator.index(GivesBool())),
    ("a subscript", lambda: [10, 20, 30, 40][GivesIndex()]),
    ("a slice", lambda: [10, 20, 30, 40, 50][GivesIndex():]),
    ("range", lambda: range(GivesIndex())),
    ("bin, hex, oct", lambda: (bin(GivesIndex()), hex(GivesIndex()), oct(GivesIndex()))),
    ("a repeat", lambda: "ab" * GivesIndex()),
    ("chr", lambda: chr(GivesIndex())),
    ("bytes of a length", lambda: bytes(GivesIndex())),
    ("math.factorial", lambda: math.factorial(GivesIndex())),
    ("round's digits", lambda: round(1.23456, GivesIndex())),
    ("%x", lambda: "%x" % GivesIndex()),  # type: ignore[str-format]
    ("int() of __index__", lambda: int(GivesIndex())),
    ("float() of __index__", lambda: float(GivesIndex())),
    ("struct's integer", lambda: struct.pack("<i", GivesIndex())),
    ("int", lambda: int(GivesInt())),
    ("int, a bool", lambda: int(GivesBool())),
    ("%d", lambda: "%d" % GivesInt()),
    ("int of an int that answers", lambda: int(IntThatGives(1))),
    ("operator.index of an int that answers", lambda: operator.index(IntThatGives(1))),
    ("float", lambda: float(GivesFloat())),
    ("math.sqrt", lambda: math.sqrt(GivesFloat())),
    ("math.fsum", lambda: math.fsum([GivesFloat(), 1.0])),
    ("%.2f", lambda: "%.2f" % GivesFloat()),
    ("complex of a float", lambda: complex(GivesFloat())),
    ("struct's double", lambda: struct.pack("<d", GivesFloat())),
    ("float of a float that answers", lambda: float(FloatThatGives(1.0))),
    ("complex", lambda: complex(GivesComplex())),
    ("cmath.sqrt", lambda: cmath.sqrt(GivesComplex())),
    ("struct's complex", lambda: struct.pack("<D", GivesComplex())),
    ("complex with an imaginary part", lambda: complex(GivesComplex(), 1)),
    ("a complex real part", lambda: complex(1j, 2)),
    ("a complex imaginary part", lambda: complex(1, 2j)),
    ("both", lambda: complex(1j, 2j)),
    ("by name", lambda: (complex(real=1j), complex(imag=1j))),
    ("a subclass's instance as the real part", lambda: complex(Pair(1, 2), 1)),
    ("a subclass made of them", lambda: Pair(1j, 2j)),
    ("no warning: one argument", lambda: (complex(1j), complex(Pair(1, 2)), int(Wide(3)), float(Long(1.5)), operator.index(Wide(4)))),
]


def shown(value: object) -> str:
    return f"{type(value).__name__} {value!r}"


for label, work in ROWS:
    called.clear()
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        result = work()
    print(f"{label}: {shown(result)}, called {called}")
    for w in caught:
        print(f"    {w.category.__name__} at line {w.lineno} of this file {w.filename == __file__}: {w.message}")
    called.clear()
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        try:
            print(f"    as an error: {shown(work())}")
        except (DeprecationWarning, struct.error) as exc:
            print(f"    as an error: {type(exc).__name__}, called {called}")

# the filters a program starts with: once for a line; what is printed names the file with its directory, left out here
kept, sys.stderr = sys.stderr, io.StringIO()
try:
    for turn in range(2):
        print("with the program's own filters:", int(GivesInt()), float(GivesFloat()), complex(1j, 2), turn)
    printed = sys.stderr.getvalue()
finally:
    sys.stderr = kept
for line in printed.splitlines():
    print("    " + line.replace(os.path.dirname(__file__) + os.sep, ""))
