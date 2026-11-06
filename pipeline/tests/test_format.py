"""The format mini-language and str.format, compiled, against CPython.

Case C-6-15 shows the behaviour by exception class, as a case must; these compare messages too, and sweep generated
specifications over generated numbers, since each flag meets every other in the C and a list of examples would not.
"""
from __future__ import annotations

from typing import Any

from pipeline.tests.test_review_2026_11_03 import same

SHOW = """def show(f):
    try:
        r = f()
        s = repr(r)
        print(s if " at 0x" not in s else "<" + type(r).__name__ + ">")
    except BaseException as e:
        print(type(e).__name__, e)
"""
WORDS = """state = 88172645463325252
def word():
    global state
    state ^= (state << 13) & 0xFFFFFFFFFFFFFFFF
    state ^= state >> 7
    state ^= (state << 17) & 0xFFFFFFFFFFFFFFFF
    return state
def choose(items):
    return items[word() % len(items)]
def spec(types):
    out = ""
    if word() % 3 == 0:
        fill = choose(["", "*", "0", " ", "é", "x"])
        out += fill + choose(["<", ">", "=", "^"]) if fill else choose(["", "<", ">", "=", "^"])
    out += choose(["", "", "+", "-", " "])
    out += choose(["", "", "", "z"])
    out += choose(["", "", "#"])
    out += choose(["", "", "0"])
    out += choose(["", "", "1", "5", "12", "25", "40"])
    out += choose(["", "", "", ",", "_"])
    out += choose(["", "", ".0", ".1", ".3", ".10", ".25", ".3,", ".3_", ".10_", ".,", "._"])
    return out + choose(types)
def attempt(v, s):
    try:
        return format(v, s)
    except (ValueError, OverflowError) as e:
        return type(e).__name__ + ": " + str(e)
"""

PROGRAMS: list[tuple[str, str]] = [
    ('messages', SHOW + r"""
for v, specs in ((1, (".2", ".2d", "z", "zd", "+c", " c", "#c", ",c", "_c", "s", "a", "y", "5s", "xx", "<<", ",x", ",b", ",o", ",X", ",n", "_n", "_c", ",_", "_,", "99999999999999999999", ".99999999999999999999f", ".", ".f", "\x00", "\x7f", "\x1f", "\x80"[0:0] + " ", "n", ".,n", "._n", ".,_", "._,", "abc", "5.2")),
                 (-1, ("c",)), (0x110000, ("c",)), (2**70, ("c",)),
                 (True, ("s", ".2", "z")),
                 (1.5, ("d", "x", "X", "o", "b", "c", "s", "y", "5d", ",d", "_x", ",n", "_n", ".,n", "._n", "ff", "<<", ".", ".f", "99999999999999999999", ".99999999999999999999f", ".2147483648f", ",_", "_,", ".,_", "._,", ",_f", "\x00", "abc")),
                 ("a", ("d", "x", "f", "e", "c", "y", "=5", "*=5", "+", "-", " ", "+5", "#", "#5", "z", ",", "_", ".,", "._", "ss", "5d", "<<", ".", "99999999999999999999", ".99999999999999999999", "\x00")),
                 (None, ("x",)), ([1], ("x",)), (object(), ("x",)), (int, ("x",)), (b"a", ("x",)), (range(1), ("x",))):
    for s in specs:
        print(repr(s), end=" ")
        show(lambda: format(v, s))
class Bad:
    def __format__(self, spec):
        return 1
class Sub(int):
    def __format__(self, spec):
        return spec * 2
class NoFormat:
    __format__ = None
for f in (lambda: format(Bad()), lambda: format(1, 2), lambda: format(1, b"x"), lambda: format(1, None), lambda: format(), lambda: format(1, "", 2), lambda: format(1, format_spec=""), lambda: format(Sub(1), "ab"), lambda: format(NoFormat()),
          lambda: (5).__format__(1), lambda: (5).__format__(None), lambda: "a".__format__(1), lambda: (1.5).__format__(1), lambda: (5).__format__(), lambda: (5).__format__("", ""), lambda: (5).__format__(x=""), lambda: int.__format__("a", ""), lambda: str.__format__(1, ""), lambda: float.__format__(1, ""), lambda: int.__format__(), lambda: object.__format__(1, "x"), lambda: object.__format__(1, 1), lambda: object.__format__(1), lambda: ascii(), lambda: ascii(1, 2), lambda: ascii(x=1)):
    show(f)
for s, a, k in (("{", (), {}), ("}", (), {}), ("{}{", (1,), {}), ("}{", (), {}), ("{0", (1,), {}), ("{0!", (1,), {}), ("{0!r", (1,), {}), ("{0!r:", (1,), {}), ("{0:", (1,), {}), ("{0:{", (1,), {}), ("{0:{}", (1, 2), {}), ("{0[", (1,), {}), ("{0[1", (1,), {}), ("{0[}", (1,), {}), ("{0.", (1,), {}), ("{0.}", (1,), {}), ("{0[]}", (1,), {}), ("{0..a}", (1,), {}), ("{0.[a]}", (1,), {}), ("{0[a]b}", ({"a": 1},), {}), ("{0[a].}", ({"a": 1},), {}), ("{0!x}", (1,), {}), ("{0!\x01}", (1,), {}), ("{0!}", (1,), {}), ("{0!rr}", (1,), {}), ("{0!r x}", (1,), {}), ("{0{}}", (1,), {}), ("{{{}", (1,), {}), ("{}", (), {}), ("{0}", (), {}), ("{1}", (1,), {}), ("{5} {9}", (1,), {}), ("{a}", (), {}), ("{a}", (), {"b": 1}), ("{} {0}", (1,), {}), ("{0} {}", (1,), {}), ("{a.b}", (), {"a": 1}), ("{0.nope}", (1,), {}), ("{0[x]}", (1,), {}), ("{0[0]}", (1,), {}), ("{0[5]}", ([1],), {}), ("{0[a]}", ([1],), {}), ("{0[z]}", ({},), {}), ("{0:{1:{2}}}", (1, 2, 3), {}), ("{0:{1:{2:{3}}}}", (1, 2, 3, 4), {}), ("{:d}", ("a",), {}), ("{:s}", (1,), {}), ("{:x}", (1.5,), {}), ("{99999999999999999999}", (), {}), ("{0[99999999999999999999]}", ([],), {}), ("{0:{1}}", (1,), {}), ("{:{a}}", (1,), {}), ("{:{0}}", (1, 2), {})):
    print(repr(s), end=" ")
    show(lambda: s.format(*a, **k))
for f in (lambda: str.format(), lambda: str.format(1), lambda: "{a}".format_map(1), lambda: "{a}".format_map({}), lambda: "{}".format_map({}), lambda: "{0}".format_map({}), lambda: "{}".format_map(), lambda: "{}".format_map({}, {}), lambda: "{}".format_map(a=1), lambda: str.format_map(1, {}), lambda: str.format_map()):
    show(f)
"""),
    ('a_sweep_of_floats', WORDS + r"""
def double():
    w = word()
    kind = w % 7
    w >>= 3
    sign = -1 if w & 1 else 1
    w >>= 1
    if kind == 0:
        return float.fromhex(("-" if sign < 0 else "") + "0x1." + hex(w & 0xFFFFFFFFFFFFF)[2:] + "p" + str((w >> 40) % 2046 - 1022))
    if kind == 1:
        return sign * (w % 100000) / 1000
    if kind == 2:
        return sign * float(w % 100000)
    if kind == 3:
        return sign * ((w % 1000) * 2 + 1) / 2
    if kind == 4:
        return sign * (w % 1000) / 1e6
    if kind == 5:
        return choose([0.0, -0.0, float("inf"), float("-inf"), float("nan"), 1.0, -1.0, 0.5, 1e16, 1e17, 1e22, 1e-5, 1e-4, 9.5, 0.95, 99.5, 999999.5, 1e6])
    return sign * 10.0 ** ((w % 40) - 20)
for i in range(6000):
    v = double()
    s = spec(["", "e", "E", "f", "F", "g", "G", "n", "%"])
    print(repr(s), repr(v), attempt(v, s))
"""),
    ('a_sweep_of_ints', WORDS + r"""
def integer():
    w = word()
    kind = w % 5
    w >>= 3
    v = {0: w % 10, 1: w % 100000, 2: w, 3: (w << 64) | word(), 4: 10 ** (w % 40)}[kind]
    return -v if word() & 1 else v
for i in range(6000):
    v = integer()
    s = spec(["", "d", "x", "X", "o", "b", "c", "n", "e", "f", "g", "%", "E", "F", "G"])
    print(repr(s), v, attempt(v, s))
    if i % 5 == 0:
        print(attempt(v, s), attempt(bool(v), s), f"{v:{s}}" if attempt(v, s)[:5] not in ("Value", "Overf") else "")
"""),
    ('a_sweep_of_strs', WORDS + r"""
for i in range(3000):
    v = choose(["", "a", "ab", "abcdef", "é", "éèê", "a b", "0123456789"])
    s = spec(["", "", "s"])
    print(repr(s), repr(v), attempt(v, s))
"""),
    ('fields_meet_their_objects', SHOW + r"""
class Trace:
    def __init__(self, name):
        self.name = name
    def __getattr__(self, n):
        print("getattr", self.name, n)
        return Trace(self.name + "." + n)
    def __getitem__(self, k):
        print("getitem", self.name, repr(k))
        return Trace(self.name + "[" + repr(k) + "]")
    def __format__(self, spec):
        print("format", self.name, repr(spec))
        return "<" + self.name + ":" + spec + ">"
    def __repr__(self):
        print("repr", self.name)
        return "R" + self.name
    def __str__(self):
        print("str", self.name)
        return "S" + self.name
t = Trace("t")
print("{0.a[1].b}".format(t))
print("{0!r:>9}".format(t), "{0!s}".format(t), "{0!a:<9}".format(t))
print("{a:{b}}".format(a=t, b=Trace("b")))
print("{a:{b!r}}".format(a=t, b=Trace("b")))
print("{a:{b.c[d]}}".format(a=t, b=Trace("b")))
print("{a}{b}{a}".format(a=Trace("x"), b=Trace("y")))
print("{0[01]}".format(t), "{0[1_0]}".format(t), "{0[ 1]}".format(t), "{0[+1]}".format(t), "{0[1.0]}".format(t))
class Seq:
    def __getitem__(self, i):
        print("seq", repr(i))
        return i
    def __len__(self):
        print("len")
        return 1
print("{0[5]}".format(Seq()), "{0[x]}".format(Seq()))
class Args(tuple if False else object):
    pass
print("{}".format(*(1,)), "{a}".format(**{"a": 1}), "{0}{1}".format(*"ab"), "{x}".format(**dict(x=1)))
show(lambda: "{0[1]}{0[0]}".format("ab"))
show(lambda: "{0[0]}".format(b"ab"))
show(lambda: "{0[0]}".format(range(3)))
show(lambda: "{0[-1]}".format(range(3)))
show(lambda: "{0[a]}".format(range(3)))
show(lambda: "{0.__class__}".format(1))
show(lambda: "{0.__class__.__name__}".format(1))
show(lambda: "{0.real.real}".format(1))
"""),
]


def pytest_generate_tests(metafunc: Any) -> None:
    if "program" in metafunc.fixturenames:
        metafunc.parametrize("program", PROGRAMS, ids=[name for name, _ in PROGRAMS])


def test_as_cpython(program: tuple[str, str]) -> None:
    same(program[1])


if __name__ == "__main__":
    for item in PROGRAMS:
        test_as_cpython(item)
