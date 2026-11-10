"""str's methods on ASCII text, compiled, against CPython.

Case C-6-14 shows the behaviour by exception class, as a case must; these compare messages too, and what stops by
name: int() of a str beyond ASCII, whose digits need the database's decimal values. Beyond ASCII the methods use the
Unicode database (runtime/src/unicode.cpp; C-3-53).
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

REFUSED = (
    ("int('\u0663')", "int() of a str beyond ASCII"),   # its digits need the database's decimal values, not written yet
)


def pytest_generate_tests(metafunc: Any) -> None:
    if "program" in metafunc.fixturenames:
        metafunc.parametrize("program", PROGRAMS, ids=[name for name, _ in PROGRAMS])
    if "refused" in metafunc.fixturenames:
        metafunc.parametrize("refused", REFUSED, ids=[text for _, text in REFUSED])


def test_as_cpython(program: tuple[str, str]) -> None:
    same(program[1])


def test_beyond_ascii() -> None:
    same(BEYOND_ASCII)


def test_what_needs_the_unicode_database_stops_by_name(refused: tuple[str, str]) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        prog = Path(tmp, "prog.py")
        prog.write_text(textwrap.dedent(refused[0]) + "\n", encoding="utf-8")
        got = subprocess.run([str(build(prog, "prog.py"))], capture_output=True, text=True, check=False, timeout=60)
    assert got.returncode == 70 and "not implemented" in got.stderr and refused[1] in got.stderr, got


if __name__ == "__main__":
    for item in PROGRAMS:
        test_as_cpython(item)
