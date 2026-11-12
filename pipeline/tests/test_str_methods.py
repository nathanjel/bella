"""str's methods on ASCII text, compiled, against CPython.

Case C-6-14 shows the behaviour by exception class, as a case must; these compare messages too. Beyond ASCII the methods
use the Unicode database (runtime/src/unicode.cpp; C-3-53), and so do int(), float() and complex() of a str, a format's
digits, a % format's errors and __slots__ names (C-6-21, whose words are compared here).
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

NO_ARGS = ("lower", "upper", "casefold", "swapcase", "capitalize", "title", "isalpha", "isalnum", "isdigit", "isdecimal", "isnumeric", "isspace", "isprintable", "isidentifier", "islower", "isupper", "istitle", "__getnewargs__", "__str__")

PROGRAMS: list[tuple[str, str]] = [
    ('messages', SHOW + f"""
for name in {NO_ARGS!r}:
    show(lambda: getattr("a", name)(1))
    show(lambda: getattr("a", name)(x=1))
    show(lambda: getattr(str, name)())
    show(lambda: getattr(str, name)(1))
""" + r"""
for f in (lambda: "a".center(), lambda: "a".center(1, 2, 3), lambda: "a".center("a"), lambda: "a".center(1.5), lambda: "a".center(2**70), lambda: "a".center(1, "ab"), lambda: "a".center(1, ""), lambda: "a".center(1, 1), lambda: "a".center(1, None), lambda: "a".center(1, b"a"), lambda: "a".center(x=1), lambda: "a".center(width=1), lambda: str.center(), lambda: str.center(1), lambda: str.center(1, 1),
          lambda: "a".ljust(), lambda: "a".ljust(1, 2, 3), lambda: "a".ljust("a"), lambda: "a".ljust(1, "ab"), lambda: "a".ljust(1, 1), lambda: "a".ljust(x=1), lambda: "a".rjust(), lambda: "a".rjust(1, 2, 3), lambda: "a".rjust("a"), lambda: "a".rjust(1, ""), lambda: "a".rjust(1, 1), lambda: "a".rjust(x=1),
          lambda: "a".zfill(), lambda: "a".zfill("a"), lambda: "a".zfill(1.5), lambda: "a".zfill(1, 2), lambda: "a".zfill(x=1), lambda: "a".zfill(2**70), lambda: str.zfill(1, 1),
          lambda: "a".removeprefix(), lambda: "a".removeprefix(1), lambda: "a".removeprefix(b"a"), lambda: "a".removeprefix(None), lambda: "a".removeprefix("a", "b"), lambda: "a".removeprefix(x="a"), lambda: "a".removesuffix(), lambda: "a".removesuffix(1), lambda: "a".removesuffix("a", "b"), lambda: "a".removesuffix(x="a"), lambda: str.removeprefix(1, "a"),
          lambda: "a".splitlines(1, 2), lambda: "a".splitlines(x=1), lambda: "a".splitlines(True, keepends=True), lambda: "a".splitlines(keepends=True, x=1), lambda: str.splitlines(1), lambda: str.splitlines(),
          lambda: "a".expandtabs("a"), lambda: "a".expandtabs(1.5), lambda: "a".expandtabs(1, 2), lambda: "a".expandtabs(x=1), lambda: "a".expandtabs(1, tabsize=2), lambda: "a\t".expandtabs(2**70), lambda: "a".expandtabs(2**31), lambda: "a".expandtabs(-(2**31) - 1), lambda: str.expandtabs(1),
          lambda: "abc".translate(), lambda: "abc".translate(1, 2), lambda: "abc".translate(x=1), lambda: "abc".translate(1), lambda: "abc".translate(None), lambda: "".translate(1), lambda: "abc".translate({97: 1.5}), lambda: "abc".translate({97: -1}), lambda: "abc".translate({97: 0x110000}), lambda: "abc".translate({97: 2**70}), lambda: "abc".translate({97: []}), lambda: "é".translate({233: []}), lambda: "é".translate({233: -1}), lambda: str.translate(1, {}),
          lambda: str.maketrans("a"), lambda: str.maketrans("a", "bc"), lambda: str.maketrans(1, "b"), lambda: str.maketrans("a", 1), lambda: str.maketrans("a", "b", 1), lambda: str.maketrans({"ab": 1}), lambda: str.maketrans({1.5: 1}), lambda: str.maketrans(), lambda: str.maketrans("a", "b", "c", "d"), lambda: str.maketrans(x=1), lambda: str.maketrans([]), lambda: str.maketrans(1), lambda: str.maketrans(None, "a"), lambda: str.maketrans({"": 1})):
    show(f)
print(type(str.maketrans).__name__)
"""),
    ('what_comes_back', SHOW + r"""
a = "abcdef"
b = "ab\tcd"
print(a.center(3) is a, a.center(6) is a, a.ljust(3) is a, a.rjust(3) is a, a.zfill(3) is a, a.lower() is a, a.upper() is a, a.title() is a, a.swapcase() is a, a.capitalize() is a, a.casefold() is a, a.removeprefix("x") is a, a.removesuffix("x") is a, a.removeprefix("") is a, a.removesuffix("") is a, a.expandtabs() is a, b.expandtabs() is b, a.splitlines()[0] is a, a.translate({}) is a, a.__str__() is a, a.__getnewargs__()[0] is a, str(a) is a, a.replace("x", "y") is a)
print(type(a.center(10)).__name__, type(a.lower()).__name__, type(a.splitlines()).__name__, type(a.__getnewargs__()).__name__, len(a.center(10)), a.center(10), a.ljust(10, "é"), a.rjust(10, "é"), "é".center(5, "è"), "éa".zfill(4), "é\tb".expandtabs(4), "é\nb".splitlines(), "é\nb".splitlines(True), "éab".removeprefix("é"), "abé".removesuffix("é"), "éaé".translate({233: "x"}), "éa".translate({97: "é"}))
class Idx:
    def __index__(self):
        return 5
print("a".center(Idx()), "a".ljust(Idx(), "*"), "a".rjust(Idx()), "a".zfill(Idx()), "a\t".expandtabs(Idx()), "abc".center(True), "abc".center(4), "abc".center(5), "abc".center(6), "abcd".center(7), "abcd".center(8), "a".center(2), "a".center(3), "a".center(4), "ab".center(3), "ab".center(4), "ab".center(5))
"""),
]

# the methods on text beyond ASCII (C-3-53 has the characters; this the str subclass and the messages around them)
BEYOND_ASCII = r"""
class S(str):
    pass
for t in ("é", "Straße", "ΣΑΣ", S("ǅungla"), "٣", "\u3000", ""):
    for name in ("lower", "upper", "title", "swapcase", "capitalize", "casefold", "isalpha", "isalnum", "isdigit", "isdecimal",
                 "isnumeric", "isspace", "isprintable", "islower", "isupper", "istitle"):
        r = getattr(t, name)()
        print(name, repr(r), type(r).__name__, end="; ")
    print()
for f in (lambda: "é".lower(1), lambda: "é".isalpha(x=1), lambda: str.upper(1), lambda: str.title()):
    try:
        f()
    except TypeError as e:
        print("TypeError", e)
"""

# what the builtins ask the Unicode database (C-6-21), in the words of their errors
DATABASE_IN_BUILTINS = r'''
def m(f, *a):
    try:
        return repr(f(*a))
    except Exception as e:
        return type(e).__name__ + ": " + str(e)
for text in ("\u0663\u0664", "\u0663x", "1\x7f\u0663", "\xbd", "\u3000", "\u0663\x00", "x" + "\u0663" * 300, "\u0663" * 5000,
             "\u0661\u0662\u0663\u0664\u0665\u0666\u0667\u0668\u0669\u0660" * 500, "\u0663_", "_\u0663", "\u0663__\u0664"):
    print(m(int, text)[:400], "|", m(float, text)[:400], "|", m(complex, text)[:400])
print(m(int, "\u0663", 99), m(int, "\u0660\u0667", 0), m(int, "\u0663\u0664", 2), m(int, "\u0660x\u0661g", 16))
print(m(format, 5, "\u0663x\u0664"), m(format, 1, "\u0669" * 30), m(format, 1.5, ".\u0669" + "\u0669" * 25 + "f"),
      m(("{" + "\u0669" * 25 + "}").format, 1), m("{\u0661}".format, 1), m("{0[\u0669\u0669\u0669]}".format, [1]))
for t in ("%\xe9", "%\u0378", "%\U0001f600", "%\x7f", "%\u2028", "%\u3000", "%\u0663d", "%(a)\xe9", "%5\xe9", "abc%\U000e0001"):
    print(repr(t), m(lambda t=t: t % 1 if "(" not in t else t % {"a": 1}))
for names in (("\xe9",), ("\u0300a",), ("1\xe9",), ("\xe9", "__dict__", "__\xe9"), ("\xe9",) * 2):
    print(m(lambda names=names: type("K", (), {"__slots__": names}).__slots__))
'''


def pytest_generate_tests(metafunc: Any) -> None:
    if "program" in metafunc.fixturenames:
        metafunc.parametrize("program", PROGRAMS, ids=[name for name, _ in PROGRAMS])


def test_as_cpython(program: tuple[str, str]) -> None:
    same(program[1])


def test_beyond_ascii() -> None:
    same(BEYOND_ASCII)


def test_the_unicode_database_in_the_builtins() -> None:
    same(DATABASE_IN_BUILTINS)


if __name__ == "__main__":
    for item in PROGRAMS:
        test_as_cpython(item)
