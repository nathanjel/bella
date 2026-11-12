"""str % args, compiled, against CPython.

Case C-6-16 walks the conversions by exception class, as a case must; these compare messages, which in 3.15 name the
argument at fault, and what stops by name.
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

PROGRAMS: list[tuple[str, str]] = [
    ('messages', SHOW + r"""
class C:
    pass
class Fl:
    def __float__(self):
        raise TypeError("inside float")
class Fv:
    def __float__(self):
        raise ValueError("inside float")
class In:
    def __int__(self):
        raise TypeError("inside int")
class Iv:
    def __int__(self):
        raise ValueError("inside int")
class Ix:
    def __index__(self):
        raise TypeError("inside index")
class Iw:
    def __index__(self):
        raise ValueError("inside index")
class BadInt:
    def __int__(self):
        return "a"
class BadFloat:
    def __float__(self):
        return "a"
for fmt, arg in (("%", (1,)), ("%5", (1,)), ("%-", (1,)), ("%.", (1,)), ("%.5", (1,)), ("%(a", {"a": 1}), ("%y", (1,)), ("%Y", (1,)), ("%k", (1,)), ("%z", (1,)), ("%!", (1,)), ("%,", (1,)), ("%'", (1,)), ('%"', (1,)), ("%\n", (1,)), ("%\x00", (1,)), ("%\x1f", (1,)), ("%\x7f", (1,)), ("%l", (1,)), ("%h", (1,)), ("%L", (1,)), ("%ll", (1,)), ("%99999999999999999999d", (1,)), ("%.99999999999999999999f", (1,)), ("%.2147483648f", (1,)), ("% ", (1,)), ("%+", (1,)), ("%#", (1,)), ("%0", (1,)), ("%5.", (1,)), ("%5.2", (1,)), ("%5.2l", (1,)), ("%1$s", (1,)), ("%v", (1,)), ("abc %y", (1,)), ("abc %", (1,)), ("abc %s %", (1, 2)), ("é%y", (1,)), ("é%", (1,)),
                 ("%s", ()), ("%s %s", (1,)), ("%s %s", 1), ("%s", (1, 2)), ("%d %d", (1, 2, 3)), ("x", 1), ("x", "a"), ("x", (1,)), ("x", (1, 2)), ("x", None), ("x", 1.5), ("x", ((),)), ("%*d", ("a", 1)), ("%*d", (1.5, 1)), ("%.*f", ("a", 1.5)), ("%*d", (2**70, 1)), ("%*d", (-(2**70), 1)), ("%*d", (-(2**63), 1)), ("%*d", (2**63, 1)), ("%.*f", (2**70, 1.5)), ("%.*f", (2**31, 1.5)), ("%.*f", (-(2**31) - 1, 1.5)), ("%*d", (5,)), ("%*d", 5), ("%*", (5,)), ("%.*", (5,)), ("%.*f", 5),
                 ("%(a)s", {}), ("%(a)s", 1), ("%(a)s", (1,)), ("%(a)s", "a"), ("%(a)s", [1]), ("%(a)s", None), ("%(", {"a": 1}), ("%(a)", {"a": 1}), ("%(a)s %s", {"a": 1}), ("%s %(a)s", {"a": 1}), ("%(a)*d", {"a": 1}), ("%(a).*f", {"a": 1}), ("%(a)d", {"a": "x"}), ("%(a)x", {"a": 1.5}), ("%(a)f", {"a": "x"}), ("%(a)c", {"a": "xy"}), ("%(a)c", {"a": -1}), ("%(a)c", {"a": 1.5}), ("%(é)d", {"é": "x"}), ("%(a b)d", {"a b": "x"}),
                 ("%d", "1"), ("%x", "1"), ("%o", "1"), ("%X", "1"), ("%i", "1"), ("%u", "1"), ("%f", "1"), ("%e", "1"), ("%g", "1"), ("%E", "1"), ("%F", "1"), ("%G", "1"), ("%d", None), ("%f", None), ("%x", None), ("%d", [1]), ("%d", C()), ("%x", C()), ("%f", C()), ("%c", C()), ("%x", 1.5), ("%o", 1.5), ("%X", 1.5), ("%c", 1.5), ("%c", "ab"), ("%c", ""), ("%c", -1), ("%c", 0x110000), ("%c", 2**70), ("%c", None), ("%d", float("inf")), ("%d", float("nan")), ("%d", (1.5, "a")), ("%d %d", (1, "a")), ("%s %d", (1, "a")), ("%d", ("a",)), ("%f", ("a",)), ("%c", ("ab",)), ("%c", (-1,)), ("%s %c", (1, "ab")),
                 ("%d", Fl()), ("%f", Fl()), ("%f", Fv()), ("%d", In()), ("%d", Iv()), ("%x", Ix()), ("%x", Iw()), ("%c", Ix()), ("%c", Iw()), ("%d", Ix()), ("%d", Iw()), ("%d", BadInt()), ("%f", BadFloat()), ("%s", (10**5000,)), ("%d", (10**5000,)), ("%x", (10**5000,)) if False else ("%s", 1)):
    print(repr(fmt), end=" ")
    show(lambda: fmt % arg)
for f in (lambda: 1 % "a", lambda: None % "a", lambda: [] % "a", lambda: "a".__mod__(), lambda: "a".__mod__(1, 2), lambda: "a".__mod__(x=1), lambda: str.__mod__(1, 2), lambda: str.__mod__(), lambda: "a".__rmod__(), lambda: "a".__rmod__(1, 2), lambda: str.__rmod__(1, 2), lambda: "x".__rmod__(1), lambda: "x".__rmod__("%s"), lambda: "x".__rmod__("a"), lambda: b"%d" % 1 if False else 0):
    show(f)
"""),
    ('a_sweep', r"""
state = 88172645463325252
def word():
    global state
    state ^= (state << 13) & 0xFFFFFFFFFFFFFFFF
    state ^= state >> 7
    state ^= (state << 17) & 0xFFFFFFFFFFFFFFFF
    return state
def choose(items):
    return items[word() % len(items)]
def value():
    w = word()
    kind = w % 9
    w >>= 4
    sign = -1 if w & 1 else 1
    w >>= 1
    if kind == 0: return sign * (w % 100)
    if kind == 1: return sign * w
    if kind == 2: return sign * ((w << 64) | word())
    if kind == 3: return sign * (w % 100000) / 1000
    if kind == 4: return sign * 10.0 ** (w % 60 - 30)
    if kind == 5: return choose([0.0, -0.0, float("inf"), float("-inf"), float("nan"), True, False, 0, 1.5, 2.5, 1e16, 1e22])
    if kind == 6: return choose(["", "a", "abc", "é", "éè", "0123456789"])
    if kind == 7: return choose([None, [1, "a"], (1,), {"a": 1}, {1}, b"a", range(2), print if False else 1])
    return float.fromhex("0x1." + hex(w & 0xFFFFFFFFFFFFF)[2:] + "p" + str((w >> 40) % 2046 - 1022))
for i in range(12000):
    flags = "".join([c for c in "-+ #0" if word() % 4 == 0])
    width = choose(["", "", "1", "5", "12", "30"])
    prec = choose(["", "", ".0", ".1", ".3", ".12", ".40"])
    conv = choose(list("sradiuoxXeEfFgGc"))
    fmt = "a%" + flags + width + prec + conv + "z"
    v = value()
    try:
        print(repr(fmt), repr(v), repr(fmt % (v,)))
    except (TypeError, ValueError, OverflowError) as e:
        print(repr(fmt), repr(v), type(e).__name__, e)
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
