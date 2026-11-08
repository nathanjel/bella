"""re and _sre, compiled, against CPython: the messages case C-7-27 does not compare, iter(callable, sentinel), repr() and isidentifier beyond Latin-1
from the Unicode tables, and what stops by name."""
from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path

from pipeline.build import build
from pipeline.tests.test_review_2026_11_03 import same

MESSAGES = r"""
import re
import _sre
def show(f):
    try:
        print(repr(f()))
    except BaseException as e:
        print(type(e).__name__, e)
p = re.compile(r"(?P<a>a)(b)?")
m = p.search("a")
s = p.scanner("a")
for fn in (lambda: p.search(), lambda: p.search(1), lambda: p.search(b"a"), lambda: re.compile(b"a").search("a"), lambda: p.search("a", "b"), lambda: p.search("a", 2**70), lambda: p.search("a", 0, 1, 2), lambda: p.search("a", nothing=1), lambda: p.search("a", string="a"), lambda: p.search(strin="a"), lambda: p.match(), lambda: p.match("a", 0, 1, 2), lambda: p.prefixmatch(), lambda: p.fullmatch(), lambda: p.fullmatch("a", 0, 1, 2), lambda: p.findall(), lambda: p.findall(1), lambda: p.finditer(), lambda: p.finditer(1), lambda: p.scanner(), lambda: p.scanner(1), lambda: p.split(), lambda: p.split(1), lambda: p.split("a", "b"), lambda: p.sub("a"), lambda: p.sub("a", 1), lambda: p.sub("a", "b", "c"), lambda: p.sub(1, "b"), lambda: p.subn("a"), lambda: p.subn(None, "a"),
           lambda: p.sub(r"\9", "a"), lambda: p.sub(r"\g<z>", "a"), lambda: p.sub(lambda m: 1, "a"), lambda: p.sub(lambda m: b"x", "a"), lambda: re.compile(b"a").sub(lambda m: "x", b"a"), lambda: re.compile(b"a").sub("x", b"a"), lambda: p.sub(b"x", "a"),
           lambda: re.Pattern(), lambda: re.Match(), lambda: type(s)(), lambda: type(_sre.template("a", ["x"]))(), lambda: type("X", (re.Pattern,), {}), lambda: type("X", (re.Match,), {}), lambda: setattr(p, "flags", 1), lambda: setattr(p, "groupindex", 1), lambda: setattr(p, "x", 1), lambda: p.nothing, lambda: p < p, lambda: p.__copy__(1), lambda: p.__deepcopy__(), lambda: p.__repr__(1), lambda: p.__hash__(1), lambda: re.Pattern.__eq__(1, p), lambda: re.Pattern.search(), lambda: re.Pattern.search(1, "a"), lambda: repr(re.Pattern.search), lambda: repr(re.Pattern.__repr__), lambda: type(re.Pattern.flags).__name__, lambda: type(re.Pattern.groupindex).__name__, lambda: repr(re.Pattern.flags), lambda: repr(re.Pattern.groupindex), lambda: repr(re.Match.regs), lambda: repr(re.Match.string), lambda: type(p.search).__name__, lambda: repr(re.Pattern)[:20], lambda: re.Pattern.__doc__, lambda: re.Match.__doc__, lambda: p.groupindex.__class__.__name__, lambda: setattr(m, "pos", 1), lambda: setattr(m, "regs", 1), lambda: setattr(m, "x", 1), lambda: m.nothing, lambda: re.Match.group(1), lambda: re.Match.group(),
           lambda: m.group(9), lambda: m.group("z"), lambda: m.group(1.5), lambda: m.group(None), lambda: m.group(x=1), lambda: m[9], lambda: m["z"], lambda: m.start(9), lambda: m.start(1, 2), lambda: m.start(x=1), lambda: m.end(9), lambda: m.end(1, 2), lambda: m.span(9), lambda: m.span(1, 2), lambda: m.groups(1, 2), lambda: m.groups(x=1), lambda: m.groupdict(1, 2), lambda: m.groupdict(x=1), lambda: m.expand(), lambda: m.expand(1), lambda: m.expand(r"\9"), lambda: m.expand(b"a"), lambda: m.expand("a", "b"), lambda: m.__copy__(1), lambda: m.__deepcopy__(), lambda: len(m), lambda: iter(m), lambda: m[0:1], lambda: s.search(1), lambda: s.match(1), lambda: s.search(x=1), lambda: s.nothing, lambda: setattr(s, "pattern", 1),
           lambda: _sre.ascii_iscased(), lambda: _sre.ascii_iscased("a"), lambda: _sre.ascii_iscased(2**70), lambda: _sre.unicode_iscased(x=1), lambda: _sre.ascii_tolower(1, 2), lambda: _sre.unicode_tolower("a"), lambda: _sre.getcodesize(1), lambda: _sre.getcodesize(x=1), lambda: _sre.compile(), lambda: _sre.compile("a", 0, 1, 0, {}, ()), lambda: _sre.compile("a", 0, [], "b", {}, ()), lambda: _sre.compile("a", 0, [], 0, 1, ()), lambda: _sre.compile("a", 0, [], 0, {}, 1), lambda: _sre.compile("a", "b", [1], 0, {}, ()), lambda: _sre.compile("a", 0, [1 << 40], 0, {}, ()), lambda: _sre.compile("a", 0, [1 << 70], 0, {}, ()), lambda: _sre.compile("a", 0, ["x"], 0, {}, ()), lambda: _sre.compile("a", 0, [-1], 0, {}, ()), lambda: _sre.compile(1, 0, [1], 0, {}, ()), lambda: _sre.compile("a", 0, [99], 0, {}, ()), lambda: _sre.template(), lambda: _sre.template("a", 1), lambda: _sre.template("a", []), lambda: _sre.template("a", ["x", 1]), lambda: _sre.template("a", ["x", "y", "z"]), lambda: _sre.template("a", ["x", -1, "z"]), lambda: _sre.template("a", ["x"], 1), lambda: _sre.template(x=1)):
    show(fn)
"""

OTHERS = r"""
def show(f):
    try:
        print(repr(f()))
    except BaseException as e:
        print(type(e).__name__, e)
values = iter([1, 2, 3, 4])
it = iter(lambda: next(values), 3)
print(type(it).__name__, iter(it) is it, next(it), list(it), list(it), next(it, "done"), repr(type(it)))
class Raises:
    def __call__(self):
        raise StopIteration
class Boom:
    def __call__(self):
        raise KeyError("k")
class Eq:
    def __eq__(self, other):
        raise ValueError("eq")
for fn in (lambda: iter(1, 2), lambda: iter(None, 2), lambda: iter(print), lambda: iter(), lambda: iter(1, 2, 3), lambda: iter(print, x=1), lambda: list(iter(Raises(), 1)), lambda: list(iter(Boom(), 1)), lambda: next(iter(lambda: 1, Eq())), lambda: type(iter(int, 1))(), lambda: type("X", (type(iter(int, 1)),), {}), lambda: type(iter(int, 1)).__next__(1), lambda: repr(type(iter(int, 1)).__next__), lambda: repr(type(iter(int, 1)).__iter__), lambda: iter(int, 0).__reduce__ if False else 0, lambda: next(iter(int, 0)), lambda: next(iter(int, 1)), lambda: list(zip(iter(int, 1), "ab"))):
    show(fn)
for text in ("é", "日本語", "Ā", "\U0001F600", " ", "​", "﻿", "\ud800", "\U000E0001", "\U0010FFFF", "á", "\xa0", "\xad", "\x7f", "\x85", "'\"", "٠", "ÿĀ", "\U00010000"):
    print(repr(text), ascii(text), f"{text!r}", repr([text]), repr({text: 1}), "%r" % text, text.isidentifier())
for name in ("a", "_", "é", "日本", "a1", "1a", "a b", "", "á", "́a", "a‌", "ª", "·", "a·", "℘", "\U00010000", "a\U000E0100", "\U000E0100", "__a__", "ⅷ", "٣", "a٣"):
    print(repr(name), name.isidentifier())
"""


def test_messages() -> None:
    same(MESSAGES)


def test_callable_iterator_and_unicode_tables() -> None:
    same(OTHERS)


def test_what_is_absent_stops_by_name() -> None:
    for body, name in (("import re\nre.compile(r'\\N{DIGIT ONE}')", "unicodedata"), ("import re\nre.compile('a').search(memoryview(b'a'))", "memoryview"), ("import re\nprint(re.compile('a').findall.__doc__)", "__doc__")):
        with tempfile.TemporaryDirectory() as tmp:
            prog = Path(tmp, "prog.py")
            prog.write_text(f"print('start')\n{body}\n", encoding="utf-8")
            got = subprocess.run([str(build(prog, "prog.py"))], capture_output=True, text=True, check=False)
        assert (got.returncode, got.stdout) == (70, "start\n") and "not implemented" in got.stderr and name in got.stderr, (body, got)


if __name__ == "__main__":
    test_messages()
    test_callable_iterator_and_unicode_tables()
    test_what_is_absent_stops_by_name()
