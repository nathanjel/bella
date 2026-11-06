"""Subclasses of str, compiled, against CPython: the messages case C-3-45 does not compare, whether an operation returns the very
object, `%` with a constant format and a tuple display (compiled as the f-string it says), and what stops by name."""
from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path

from pipeline.build import build
from pipeline.tests.test_review_2026_11_03 import same

MESSAGES = r"""
def show(f):
    try:
        print(repr(f()))
    except BaseException as e:
        print(type(e).__name__, e)
class S(str):
    pass
class BadStr(str):
    def __str__(self):
        return 1
class BadRepr(str):
    def __repr__(self):
        return 1
class Unhashable(str):
    __hash__ = None
class WithSlots(str):
    __slots__ = ("a",)
for fn in (lambda: S(1, 2), lambda: S(1, 2, 3, 4), lambda: S(b"a", 1), lambda: S("a", "ascii"), lambda: S(nothing=1), lambda: str.__new__(int), lambda: str.__new__(1), lambda: str.__new__(), lambda: object.__new__(S), lambda: int.__new__(S), lambda: tuple.__new__(S),
           lambda: type("X", (str, int), {}), lambda: type("X", (str, bytes), {}), lambda: type("X", (str, list), {}), lambda: type("X", (S, dict), {}), lambda: setattr("a", "x", 1), lambda: vars("a"), lambda: S("a").nothing, lambda: setattr(WithSlots("a"), "c", 1), lambda: WithSlots("a").a, lambda: WithSlots("a").__dict__,
           lambda: str(BadStr("x")), lambda: print(BadStr("x")), lambda: "%s" % BadStr("x"), lambda: "%s" % (BadStr("x"),), lambda: f"{BadStr('x')}", lambda: format(BadStr("x")), lambda: repr(BadRepr("x")), lambda: "%r" % BadRepr("x"), lambda: [BadRepr("x")].__repr__(), lambda: hash(Unhashable("a")), lambda: {Unhashable("a"): 1}, lambda: {"a": 1}.get(Unhashable("a")),
           lambda: "".join([1]), lambda: S("a").join([1]), lambda: S("a") + 1, lambda: 1 + S("a"), lambda: S("a") * "b", lambda: S("a") < 1, lambda: 1 < S("a"), lambda: S("a")[5], lambda: S("a")["b"], lambda: S("a").upper(1), lambda: str.upper(1), lambda: str.upper(), lambda: str.__add__(), lambda: str.__add__(1, "a"), lambda: str.__add__("a", 1), lambda: str.__add__("a", "b", "c"), lambda: str.__len__(), lambda: str.__len__(1), lambda: str.__len__("a", 1), lambda: str.__iter__(1), lambda: str.__hash__(1), lambda: str.__repr__(1), lambda: str.__repr__("a", 1), lambda: str.__contains__("a", 1), lambda: str.__contains__(1, "a"), lambda: str.__getitem__("a", "b"), lambda: str.__getitem__("a", 5), lambda: str.__str__(1), lambda: str.__format__("a", 1),
           lambda: repr(str.__len__), lambda: repr(str.__new__)[:30], lambda: str.__len__.__objclass__, lambda: repr("a".__len__)[:35], lambda: type(S("a").__len__).__name__, lambda: S("a").__len__.__self__, lambda: S("a").__len__.__name__, lambda: S.__len__ is str.__len__,
           lambda: __import__("sys").intern(S("a")), lambda: ord(S("ab")), lambda: int(S("a")), lambda: float(S("a")), lambda: bytes(S("a")), lambda: S("a").encode(1), lambda: S("%d") % "x", lambda: "%s %s" % ("a",), lambda: "%s" % ("a", "b"), lambda: "%y" % ("a",), lambda: "%" % ("a",), lambda: "%5" % ("a",), lambda: "%*s" % ("a", "b"), lambda: "%d" % ("a",), lambda: "%(a)s" % ("a",)):
    show(fn)
"""

IDENTITY = r"""
class S(str):
    pass
class G(str):
    def __str__(self):
        return S("sub")
def of(v):
    return (type(v).__name__, v)
s = "abcd"
t = S("t")
print(("%s" % s) is s, ("%s" % (s,)) is s, (s % ()) is s, s.format() is s, "{}".format(s) is s, f"{s}" is s, f"{t}" is t, type(f"{t}").__name__, s + "" is s, "" + s is s, s[:] is s, s[0:] is s, s[::1] is s, s[::-1] is s, s[0:4] is s, s[0:3] is s, s * 1 is s, s.strip() is s, s.replace("z", "y") is s, str(s) is s, s.__str__() is s, "".join([s]) is s, s.center(1) is s, s.zfill(1) is s, s.ljust(1) is s, s.removeprefix("z") is s, s.partition("z")[0] is s, s.rpartition("z")[2] is s, s.split()[0] is s, s.rsplit()[0] is s, s.splitlines()[0] is s, s.expandtabs() is s, s.format_map({}) is s, s.__format__("") is s, format(s) is s)
print(of(t + ""), of("" + t), of(t[:]), of(t[0:1]), of(t * 1), of(t.strip()), of(t.format()), of(t.format_map({})), of(t % ()), of("%s" % t), of("%s" % (t,)), of("{}".format(t)), of(f"{t}"), of(f"{t!s}"), of(f"{t:}"), of("".join([t])), of(t.partition("z")[0]), of(t.rpartition("z")[2]), of(t.partition("zzzz")[0]), of(t.split()[0]), of(t.__str__()), of(t.__format__("")), of(format(t)))
print(of("%s" % G("x")), of("%s" % (G("x"),)), of("%r" % G("x")), of("{}".format(G("x"))), of(f"{G('x')}"), of(f"{G('x')!s}"), of(str(G("x"))), of(format(G("x"))), of(G("x").__format__("")))
print("%s" % (1,), "%s %s" % (1, 2), "%5s|%-5s|%05s|%+s|% s|%#s" % ("a", "b", "c", "d", "e", "f"), "%.1s|%5.1s|%-5.1s" % ("ab", "cd", "ef"), "%r|%a|%5r" % ("a", "é", "b"), "%%|%s|%%" % ("a",), "%123s" % ("a",), "%1234s" % ("a",), "%.123s" % ("a",), "%.1234s" % ("a",), "%s" % (None,), "%s" % ((1, 2),), "%s" % ([1],), "x%sy%sz" % (1, 2), "é%sé" % ("ü",), f"{'a'!s:>3}")
"""


def test_messages() -> None:
    same(MESSAGES)


def test_what_comes_back_as_itself() -> None:
    same(IDENTITY)


def test_what_is_absent_stops_by_name() -> None:
    prelude = "class S(str):\n    pass\nclass H(str):\n    def __hash__(self):\n        return 1\nclass O:\n    pass\no = O()\no.x = 1\nprint('start')\n"
    for body, name in (("setattr(o, S('x'), 1)", "storing an attribute"), ("getattr(o, H('x'))", "__hash__ or __eq__"), ("delattr(o, H('x'))", "__hash__ or __eq__"), ("def f(**k):\n    pass\nf(**{S('a'): 1})", "keyword"), ("dict(**{S('a'): 1})", "keyword"), ("type(S('N'), (), {})", "class named"), ("type('N', (), {S('m'): 1})", "namespace")):
        with tempfile.TemporaryDirectory() as tmp:
            prog = Path(tmp, "prog.py")
            prog.write_text(prelude + body + "\n", encoding="utf-8")
            got = subprocess.run([str(build(prog, "prog.py"))], capture_output=True, text=True, check=False)
        assert (got.returncode, got.stdout) == (70, "start\n") and "not implemented" in got.stderr and name in got.stderr, (body, got)


if __name__ == "__main__":
    test_messages()
    test_what_comes_back_as_itself()
    test_what_is_absent_stops_by_name()
