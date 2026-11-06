"""complex, compiled, against CPython.

Case C-6-17 walks complex by exception class, as a case must, and rounds what libm computes, as its expectations are
recorded; these compare messages and every digit, on the same machine: the arithmetic's corners, generated formats and
generated strings.
"""
from __future__ import annotations

import subprocess
import tempfile
import textwrap
from pathlib import Path
from typing import Any

from pipeline.build import build
from pipeline.tests.test_review_2026_11_03 import same

SHOW = """def show(f):
    try:
        r = f()
        s = repr(r)
        print(s if " at 0x" not in s else "<" + type(r).__name__ + ">")
    except BaseException as e:
        print(type(e).__name__, e)
"""

PROGRAMS: list[tuple[str, str]] = [
    ('messages', SHOW + r"""
inf = float("inf")
class Neither:
    pass
class BadComplex:
    def __complex__(self):
        return 1
class BadFloat:
    def __float__(self):
        return 1
class Raises:
    def __complex__(self):
        raise ValueError("inside complex")
class NoneFloat:
    __float__ = None
class C(complex):
    pass
for f in (lambda: complex(None), lambda: complex([]), lambda: complex(b"1"), lambda: complex(Neither()), lambda: complex(BadComplex()), lambda: complex(BadFloat()), lambda: complex(Raises()), lambda: complex(NoneFloat()), lambda: complex(2**2000), lambda: complex("1", 2), lambda: complex(1, "2"), lambda: complex("1", "2"), lambda: complex(real="1"), lambda: complex(imag="1"), lambda: complex(None, 1), lambda: complex(1, None), lambda: complex(1, 2, 3), lambda: complex(x=1), lambda: complex(1, 2, x=1), lambda: complex(1, real=1), lambda: complex(1, 2, imag=1), lambda: complex(real=1, imag=2, x=3), lambda: complex(Neither(), 1), lambda: complex(1, Neither()), lambda: complex(BadFloat(), 1), lambda: complex(1, BadFloat()), lambda: complex(2**2000, 1), lambda: complex(1, 2**2000),
          lambda: complex(""), lambda: complex("a"), lambda: complex("1_"), lambda: complex("_1"), lambda: complex("1__0"), lambda: complex("1\x00"), lambda: complex("(1"), lambda: complex("1e400j"), lambda: complex("1_+1j"), lambda: complex(" 1_ "),
          lambda: complex.from_number("1"), lambda: complex.from_number(None), lambda: complex.from_number(), lambda: complex.from_number(1, 2), lambda: complex.from_number(number=1), lambda: complex.from_number(Neither()), lambda: complex.from_number(BadComplex()), lambda: complex.from_number(BadFloat()), lambda: complex.from_number(2**2000), lambda: C.from_number("1"),
          lambda: 1j / 0, lambda: 1j / 0.0, lambda: 1j / 0j, lambda: 1 / 0j, lambda: 1.0 / 0j, lambda: 0j / 0j, lambda: 2**2000 + 1j, lambda: 1j + 2**2000, lambda: 1j * 2**2000, lambda: 1j / 2**2000, lambda: 2**2000 / 1j, lambda: 2**2000 ** 1j, lambda: 1j ** 2**2000, lambda: 1j == 2**2000,
          lambda: 0j ** -1, lambda: 0j ** -1.5, lambda: 0j ** 1j, lambda: 0 ** 1j, lambda: (1e200 + 1e200j) ** 2, lambda: (1e200 + 1e200j) ** 2.5, lambda: 2 ** (1e4 + 1j), lambda: pow(1j, 2, 3), lambda: pow(2, 1j, 3), lambda: pow(2, 3, 1j), lambda: pow(1.5, 1j, 3), lambda: pow(1j, 1.5, 3), lambda: pow(1, 1.5, 1j), lambda: pow("a", 2, 1j), lambda: pow("a", 1j, 3), lambda: pow(1j, "a", 3), lambda: pow(1j, "a"), lambda: 1j ** "a", lambda: "a" ** 1j, lambda: pow(1j, 1j, 1j), lambda: pow(1j, 2, None), lambda: abs(complex(1e308, 1e308)), lambda: complex(1e308, 1e308).__abs__(),
          lambda: 1j % 1, lambda: 1 % 1j, lambda: 1j // 1, lambda: 1 // 1j, lambda: divmod(1j, 1), lambda: divmod(1, 1j), lambda: 1j < 1, lambda: 1 < 1j, lambda: 1j <= 1j, lambda: 1j > 1.5, lambda: 1.5 >= 1j, lambda: 1j & 1, lambda: 1 | 1j, lambda: 1j ^ 1j, lambda: 1j << 1, lambda: 1 >> 1j, lambda: ~1j, lambda: 1j @ 1j, lambda: int(1j), lambda: float(1j), lambda: round(1j), lambda: round(1j, 1), lambda: [1].__getitem__(1j), lambda: [1] * 1j, lambda: 1j * [1], lambda: "a" * 1j, lambda: "a" + 1j, lambda: 1j + "a", lambda: 1j + None, lambda: None + 1j, lambda: 1j - [], lambda: 1j * {}, lambda: 1j / "a", lambda: "a" / 1j, lambda: range(1j), lambda: 1j.__float__(), lambda: 1j.__int__(), lambda: 1j.__mod__(1), lambda: 1j.__floordiv__(1), lambda: (1j).nothing, lambda: setattr(1j, "real", 1), lambda: setattr(1j, "imag", 1), lambda: setattr(1j, "x", 1), lambda: delattr(1j, "real"), lambda: delattr(1j, "x"), lambda: "%d" % 1j, lambda: "%x" % 1j, lambda: "%f" % 1j, lambda: "%c" % 1j, lambda: "%e" % (1j,), lambda: hex(1j), lambda: chr(1j),
          lambda: complex.__add__(1, 1), lambda: complex.__add__(), lambda: complex.__add__(1j), lambda: complex.__add__(1j, 1, 2), lambda: complex.__add__(1j, x=1), lambda: complex.__neg__(1), lambda: complex.__neg__(1j, 1), lambda: complex.__repr__(1), lambda: complex.__hash__(1), lambda: complex.__eq__(1, 1j), lambda: complex.__eq__(1j), lambda: complex.__pow__(1j, 2, 3), lambda: complex.__pow__(1j), lambda: complex.__pow__(1j, 2, 3, 4), lambda: complex.__rpow__(1j, 2, 3), lambda: complex.__rpow__(1j), lambda: complex.__pow__(1j, 2, x=1), lambda: complex.conjugate(1), lambda: complex.conjugate(1j, 1), lambda: complex.__complex__(1), lambda: complex.__getnewargs__(1), lambda: complex.__format__(1, ""), lambda: complex.__format__(1j), lambda: complex.__format__(1j, 1), lambda: (1j).conjugate(1), lambda: (1j).__complex__(1), lambda: (1j).__getnewargs__(1), lambda: complex.real.__get__(1), lambda: complex.imag.__get__("a"), lambda: complex.real.__set__(1j, 1), lambda: complex.real.__delete__(1j),
          lambda: C("a"), lambda: C(None), lambda: C(1, 2, 3), lambda: complex.__new__(int), lambda: complex.__new__(1), lambda: complex.__new__(), lambda: complex.__new__(object), lambda: complex.__new__(complex, 1, 2, 3), lambda: type("X", (complex, int), {}), lambda: type("X", (complex, float), {}), lambda: type("X", (float, complex), {}), lambda: type("X", (C, int), {}),
          lambda: sum([1j, "a"]), lambda: sum([1j, None]), lambda: sum([1j, 2**2000]), lambda: sum([2**2000, 1j]), lambda: sum(["a"], 1j), lambda: sum([1j], "a"), lambda: sum([1.5, "a"], 1j), lambda: sum([1.5, 1j, "a"]),
          lambda: format(1j, "05"), lambda: format(1j, "010.2f"), lambda: format(1j, "0"), lambda: format(1j, "=10"), lambda: format(1j, "*=10"), lambda: format(1j, "d"), lambda: format(1j, "%"), lambda: format(1j, "s"), lambda: format(1j, ",d"), lambda: format(1j, ",s"), lambda: format(1j, "x"), lambda: format(C(1), "d"), lambda: format(1j, ".2147483648f"), lambda: format(1j, ",_"), lambda: format(1j, "_,")):
    show(f)
"""),
    ('corners', r"""
inf = float("inf")
nan = float("nan")
vals = (0.0, -0.0, 1.0, -1.0, 0.5, 1e308, 5e-324, inf, -inf, nan)
def show(f, *args):
    try:
        print(f(*args), end=" ")
    except (ZeroDivisionError, OverflowError) as e:
        print(type(e).__name__, e, end=" ")
    print()
add = lambda a, b: a + b
sub = lambda a, b: a - b
mul = lambda a, b: a * b
div = lambda a, b: a / b
power = lambda a, b: a ** b
ops = (add, sub, mul, div, power)
complexes = [complex(a, b) for a in vals for b in vals]
for z in complexes:
    print(z, -z, +z, z.conjugate(), bool(z), z == z, z != z, z == z.real, z == 1, end=" ")
    show(abs, z)
    if z == z:
        print(hash(z), repr(z), str(z), format(z), format(z, ".3g"), format(z, "e"), format(z, "+.1f"), format(z, ">30"), z.__getnewargs__())
for z in complexes[::3]:
    for w in complexes[::7]:
        for op in ops:
            show(op, z, w)
for z in complexes[::2]:
    for r in vals + (0, 1, -1, 2, -2, 3, 100, -100, 101, True, False, 2**70, -(2**70)):
        for op in ops:
            show(op, z, r)
            show(op, r, z)
for z in complexes[::5]:
    for n in range(-5, 12):
        show(power, z, n)
        show(power, z, float(n))
for base in (-8.0, -8, -1.5, -1, -2.0, -0.5, -1e308, -5e-324):
    for e in (0.5, 1 / 3, 1.5, -0.5, 2.5, 1e308, 1e-308, 0.1):
        show(power, base, e)
        show(pow, base, e)
"""),
    ('a_format_sweep', r"""
state = 88172645463325252
def word():
    global state
    state ^= (state << 13) & 0xFFFFFFFFFFFFFFFF
    state ^= state >> 7
    state ^= (state << 17) & 0xFFFFFFFFFFFFFFFF
    return state
def choose(items):
    return items[word() % len(items)]
def part():
    w = word()
    kind = w % 6
    w >>= 3
    sign = -1 if w & 1 else 1
    w >>= 1
    if kind == 0: return sign * float(w % 100)
    if kind == 1: return sign * (w % 100000) / 1000
    if kind == 2: return sign * 10.0 ** (w % 60 - 30)
    if kind == 3: return choose([0.0, -0.0, float("inf"), float("-inf"), float("nan"), 1.5, 2.5, 1e16, 1e22, 1e-5])
    if kind == 4: return sign * float(w)
    return float.fromhex("0x1." + hex(w & 0xFFFFFFFFFFFFF)[2:] + "p" + str((w >> 40) % 2046 - 1022))
for i in range(12000):
    fill = choose(["", "", "", "*", "é"])
    align = choose(["", "", "<", ">", "^"]) if fill == "" else choose(["<", ">", "^"])
    sign = choose(["", "", "+", "-", " "])
    z = choose(["", "", "", "z"])
    alt = choose(["", "", "", "#"])
    width = choose(["", "", "1", "12", "30", "60"])
    sep = choose(["", "", "", ",", "_"])
    prec = choose(["", "", ".0", ".1", ".3", ".12"])
    fsep = choose(["", "", "", ",", "_"]) if prec else ""
    if fsep:
        prec = prec + fsep
    conv = choose(["", "", "e", "E", "f", "F", "g", "G", "n"])
    spec = fill + align + sign + z + alt + width + sep + prec + conv
    v = complex(part(), part())
    try:
        print(repr(spec), repr(v), repr(format(v, spec)))
    except ValueError as e:
        print(repr(spec), repr(v), "ValueError", e)
"""),
    ('a_string_sweep', r"""
state = 2463534242
def word():
    global state
    state ^= (state << 13) & 0xFFFFFFFFFFFFFFFF
    state ^= state >> 7
    state ^= (state << 17) & 0xFFFFFFFFFFFFFFFF
    return state
pieces = ["1", "0", "2.5", ".5", "5.", "1e5", "1E-5", "1e400", "1_000", "_", "+", "-", "j", "J", "(", ")", " ", "\t", "inf", "nan", "infinity", "INF", "e", ".", "\x00", "a"]
for i in range(30000):
    text = "".join([pieces[word() % len(pieces)] for k in range(word() % 6)])
    try:
        print(repr(text), repr(complex(text)))
    except ValueError as e:
        print(repr(text), "ValueError", e)
"""),
    ('a_sum_sweep', r"""
state = 123456789123
def word():
    global state
    state ^= (state << 13) & 0xFFFFFFFFFFFFFFFF
    state ^= state >> 7
    state ^= (state << 17) & 0xFFFFFFFFFFFFFFFF
    return state
class I(int):
    pass
class F(float):
    pass
class C(complex):
    pass
def item():
    w = word()
    kind = w % 12
    w >>= 4
    sign = -1 if w & 1 else 1
    w >>= 1
    if kind == 0: return sign * (w % 100)
    if kind == 1: return sign * w
    if kind == 2: return sign * 10.0 ** (w % 40 - 20)
    if kind == 3: return sign * 1e100
    if kind == 4: return complex(sign * 1e100, w % 3)
    if kind == 5: return complex(w % 3, sign * 1e100)
    if kind == 6: return complex(sign * (w % 7), sign * 0.1)
    if kind == 7: return I(sign * (w % 9))
    if kind == 8: return F(sign * 0.1)
    if kind == 9: return C(sign * 1.5, 0.25)
    if kind == 10: return True
    return [float("inf"), float("-inf"), -0.0, 0.0, complex(-0.0, -0.0), complex(float("inf"), 0), complex(0, float("-inf"))][w % 7]
for i in range(4000):
    items = [item() for k in range(word() % 8)]
    start = [0, 0.0, 0j, complex(-0.0, -0.0), -0.0, 1, 1.5, 1j, C(1, 1), F(0.5), I(2)][word() % 11]
    r = sum(items, start)
    print(type(r).__name__, r)
"""),
]

REFUSED = (
    ("complex(1j, 2)", "DeprecationWarning"),
    ("complex(2, 1j)", "DeprecationWarning"),
    ("complex(real=1j)", "DeprecationWarning"),
    ("complex('\\xe9')", "beyond ASCII"),
    ("class C(complex):\n    pass\nclass D:\n    def __complex__(self):\n        return C(1)\ncomplex(D())", "subclass of complex"),
)


def pytest_generate_tests(metafunc: Any) -> None:
    if "program" in metafunc.fixturenames:
        metafunc.parametrize("program", PROGRAMS, ids=[name for name, _ in PROGRAMS])
    if "refused" in metafunc.fixturenames:
        metafunc.parametrize("refused", REFUSED, ids=[text for _, text in REFUSED])


def test_as_cpython(program: tuple[str, str]) -> None:
    same(program[1])


def test_what_is_not_there_yet_stops_by_name(refused: tuple[str, str]) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        prog = Path(tmp, "prog.py")
        prog.write_text(textwrap.dedent(refused[0]) + "\n", encoding="utf-8")
        got = subprocess.run([str(build(prog, "prog.py"))], capture_output=True, text=True, check=False, timeout=60)
    assert got.returncode == 70 and "not implemented" in got.stderr and refused[1] in got.stderr, got


if __name__ == "__main__":
    for item in PROGRAMS:
        test_as_cpython(item)
