"""A warning shown by CPython's C itself, compiled against CPython (D-27; case C-7-86; the author's decision of 2026-11-14).

When the import of `warnings` fails, CPython's C prints a warning itself (Python/_warnings.c, show_warning) and reads the
source line from the file (Python/traceback.c, display_source_line), in the encoding the tokenizer finds in the file's first
lines (Parser/tokenizer/file_tokenizer.c, _PyTokenizer_FindEncodingFilename). A compiled program that holds no `warnings`
module prints the same way; that is what C-7-86 checks, against CPython with the import blocked. Here the import is blocked
by the program itself (`sys.modules["warnings"] = None`), which CPython and a compiled program answer alike whatever the
program imports, so the two are compared directly: the source line over files of every shape the tokenizer tells apart, where
the file is looked for, an `io` whose functions the program replaced, what is written piece by piece, and what goes wrong on
the way. And the stops that stay: the program's own import of a module it does not hold, before a warning and after one.

Run under pytest or directly: python3 -m pipeline.tests.test_warnings_without_the_module
"""
from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path

from pipeline.build import build
from pipeline.tests.test_compiled_imports import same

HEAD = r"""
import os
import sys

import _warnings

sys.modules["warnings"] = None      # the import fails, as for a module that is not installed: the C prints


class Pieces:
    def __init__(self):
        self.written = []

    def write(self, text):
        self.written.append(text)
        return len(text)


def shown(name, lineno, whole=False):
    catcher = Pieces()
    old = sys.stderr
    sys.stderr = catcher
    try:
        _warnings.warn_explicit("m", UserWarning, name, lineno)
    finally:
        sys.stderr = old
    return catcher.written if whole else catcher.written[6:]      # the pieces after "name:lineno: UserWarning: m\n"
"""

# Each file is asked for its first five lines and one far beyond its end. Z is one character in UTF-8 and two in Latin-1, so
# the line that has it says which encoding was found; E is no UTF-8 at all, so a file read as UTF-8 gives no line.
FILES = HEAD + r"""
Z = b"\xc5\xbc"
E = b"\xe9"
MARK = b"\xef\xbb\xbf"
LATIN = b"# coding: latin-1\n"
UTF = b"# coding: utf-8\n"
FILES = {
    "plain": b"x = 1\n\ty = '" + Z + b"'\n\n  z = 3  \nlast",
    "empty": b"",
    "one_newline": b"\n",
    "mark": MARK + b"x = '" + Z + b"'\ny = 2\n",
    "mark_only": MARK,
    "half_mark": b"\xef\xbbx = 1\n",
    "first_line": b"# -*- coding: latin-1 -*-\nx = '" + E + b"'\n",
    "second_line": b"#!/usr/bin/python\n# vim: set fileencoding=latin-1 :\nx = '" + E + b"'\n",
    "after_an_empty_line": b"\n# coding=latin-1\nx = '" + E + b"'\n",
    "after_white_space": b" \t\x0c\n# coding=latin-1\nx = '" + E + b"'\n",
    "after_code": b"import os\n# coding=latin-1\nx = '" + Z + b"'\n",
    "third_line": b"#\n#\n# coding=latin-1\nx = '" + Z + b"'\n",
    "behind_code": b"x = 1  # coding: latin-1\ny = '" + Z + b"'\n",
    "white_space_before_it": b" \t\x0c# coding: latin-1\ny = '" + Z + b"'\n",
    "a_space_before_the_colon": b"# coding : latin-1\ny = '" + Z + b"'\n",
    "an_empty_one_first": b"# coding: , coding=latin-1\ny = '" + Z + b"'\n",
    "no_comment": b"coding: latin-1\ny = '" + Z + b"'\n",
    "in_a_string": b"'# coding: latin-1'\ny = '" + Z + b"'\n",
    "mark_and_another": MARK + b"# coding: latin-1\nx = '" + Z + b"'\n",
    "mark_and_the_same": MARK + b"# coding: utf-8\nx = '" + Z + b"'\n",
    "crlf": b"# coding: latin-1\r\nx = '" + E + b"'\r\ny = 2\r\n",
    "cr": b"# coding: latin-1\rx = '" + E + b"'\ry = 2\r",
    "cr_second": b"#\r# coding: latin-1\rx = '" + E + b"'\r",
    "nul_before": b"#\x00 coding: latin-1\nx = '" + Z + b"'\n",
    "nul_after": b"# coding: latin-1 \x00\nx = '" + Z + b"'\n",
    "nul_then_second": b"# \x00\n# coding: latin-1\nx = '" + Z + b"'\n",
    "nul_in_the_second": b"#\n# coding: latin-1 \x00\nx = '" + Z + b"'\n",
    "short_comment_first": b"#a\n# coding: latin-1\nx = '" + Z + b"'\n",
    "short_code_first": b"a\n# coding: latin-1\nx = '" + Z + b"'\n",
    "six_before_the_end": b"#coding=latin-1",
    "five_before_the_end": b"#coding:a",
    "no_newline_second": b"#\n#coding=latin-1",
    "long_first_line": b"#" + b"a" * 5000 + b"\n# coding: latin-1\nx = '" + Z + b"'\n",
    "cr_at_the_block_end": b"#" + b"a" * 4094 + b"\r\n# coding: latin-1\nx = '" + Z + b"'\n",
    "cr_alone_at_the_block_end": b"#" + b"a" * 4094 + b"\r# coding: latin-1\rx = '" + Z + b"'\r",
    "long_spec_line": b"#" + b" " * 9000 + b"coding: latin-1\nx = '" + Z + b"'\n",
    "bad_bytes_here": b"x = 1\ny = '\xff'\n",
    "bad_bytes_later": b"x = 1\n" + b"y = 2\n" * 5 + b"z = '\xff'\n",
    "bad_bytes_far": b"x = 1\n" + b"# filler\n" * 3000 + b"z = '\xff'\n",
    "ascii_and_ascii": b"# coding: ascii\nx = 1\n",
    "ascii_and_utf8": b"# coding: ascii\nx = '" + Z + b"'\n",
    "ascii_and_far": b"# coding: ascii\nx = 1\n" + b"# filler\n" * 3000 + b"z = '" + Z + b"'\n",
}
# what the lexer makes of the first lines: an encoding found and an error after it is no line at all
for label, head in (("bare", b""), ("mark", MARK), ("latin", LATIN), ("utf", UTF), ("second", b"#!x\n" + LATIN)):
    for what, body in (("a_bad_token", b"x = $\ny = 2\n"), ("an_open_string", b"x = 'abc\ny = 2\n"), ("an_unmatched_bracket", b")\ny = 2\n"),
                       ("a_bad_number", b"x = 1_\ny = 2\n"), ("a_long_string_open", b"\"\"\"doc\nmore\n"), ("a_long_string", b"\"\"\"doc\nmore\n\"\"\"\ny = 2\n"),
                       ("a_nul_in_the_string", b"\"\"\"doc\n\x00more\n\"\"\"\ny = 2\n"), ("a_nul_later", b"x = 1\ny = 2\n\x00\n"), ("a_nul_second", b"x = 1\n\x00y = 2\n"),
                       ("tabs_and_spaces", b"if x:\n\ty = 1\n        z = 2\n"), ("a_dedent", b"if x:\n        y = 1\n    z = 2\n"), ("an_indent", b"  x = 1\ny = 2\n"),
                       ("a_continuation", b"x = 1 + \\\n  2\ny = 3\n"), ("a_continuation_then_junk", b"x = 1 \\ junk\ny = 3\n"), ("a_continuation_at_the_end", b"x = 1 \\"),
                       ("comments_only", b"# one\n# two\n# three\n"), ("empty_lines", b"\n\n\nx = 1\n"), ("a_bad_token_third", b"# one\n\nx = $\n"),
                       ("bad_bytes_second", b"x = 1\ny = '\xff'\n"), ("bad_bytes_first", b"x = '\xff'\ny = 1\n"), ("an_fstring", b"x = f'{a!z}'\ny = 1\n"),
                       ("an_open_fstring", b"x = f'{a\ny = 1\n"), ("a_form_feed", b"\x0cx = 1\ny = 2\n"), ("a_cr_in_a_string", b"x = 'a\rb'\ny = 2\n"),
                       ("nothing", b""), ("an_exclamation", b"!\ny = 2\n"), ("a_dollar_second", b"x = 1\n$\n"), ("a_backquote", b"`x`\ny = 2\n"),
                       ("an_escape", b"x = '\\d'\ny = 2\n"), ("a_big_indent", b"if x:\n" + b"".join(b" " * (n + 1) + b"if x:\n" for n in range(101)) + b"y = 1\n"),
                       ("an_octal", b"x = 0777\ny = 2\n"), ("an_identifier", b"x\xc2\xa0 = 1\ny = 2\n"), ("a_closing_brace", b"x = (1}\ny = 2\n")):
        FILES[label + "_then_" + what] = head + body
for spelling in (b"UTF_8", b"utf-8-sig", b"Utf-8-Unix", b"utf-8x", b"utf8", b"Latin_1", b"ISO_8859_1", b"iso-latin-1-unix", b"latin-1-dos", b"LATIN-1x", b"latin1",
                 b"iso-8859-1-and-a-long-tail", b"nonesuch", b"US-ASCII", b"latin-1.x", b"-", b"..", b"L1"):
    FILES["spelled_" + spelling.decode()] = b"# coding: " + spelling + b"\nx = '" + Z + b"'\ny = 'a'\n"

for name, data in FILES.items():
    with open(name, "wb") as out:
        out.write(data)
    for lineno in (1, 2, 3, 4, 5, 3008):
        print(name, lineno, ascii(shown(name, lineno)))
for lineno in (0, -1, 2**31 - 1):
    print("line", lineno, ascii(shown("plain", lineno)))
print("in sys.modules:", sys.modules["warnings"])
"""

# io.open by the name given; when that fails, by the last part of the name in each directory of sys.path
WHERE = HEAD + r"""
os.makedirs("lib/inner", exist_ok=True)
os.makedirs("adir", exist_ok=True)
for name, data in (("plain", b"plain = 1\n"), ("lib/deep.py", b"deep = 1\n"), ("lib/inner/deeper.py", b"deeper = 1\n")):
    with open(name, "wb") as out:
        out.write(data)
here = os.getcwd()
kept = sys.path[:]
for label, path in (("as it is", kept), ("with lib", kept + ["lib"]), ("with lib/", kept + ["lib/"]), ("absolute", kept + [here + "/lib"]),
                    ("things that are no str first", [5, b"lib", None, "lib"]), ("a NUL in one", ["li\0b", "lib"]), ("too long", ["x" * 5000, "lib"]),
                    ("almost too long", ["x" * 4080, "lib"]), ("an empty one", [""]), ("a tuple", ("lib",)), ("inner first", ["lib/inner", "lib"])):
    sys.path = path
    for name in ("deep.py", "nowhere/deep.py", "/nowhere/deep.py", "lib/deep.py", "nowhere/lib/deep.py", "deeper.py", "inner/deeper.py", "adir", "adir/", "",
                 "plain", "x/plain", "nowhere\0/deep.py", "nowhere/deep.py\0x", "\udcff/deep.py", "\ud800/deep.py"):
        print(label, ascii(name), ascii(shown(name, 1)))
del sys.path
print("no sys.path", ascii(shown("nowhere/deep.py", 1)), ascii(shown("plain", 1)))
sys.path = kept
os.chdir("lib")
print("another working directory", ascii(shown("deep.py", 1)), ascii(shown("plain", 1)), ascii(shown(here + "/plain", 1)))
os.chdir(here)
"""

# The C reads through io.open and io.TextIOWrapper as the module has them when it prints, and calls what the program put there
REPLACED = HEAD + r"""
import io

with open("plain", "wb") as out:
    out.write(b"first = 1\n    second = 2\n")
with open("spec", "wb") as out:
    out.write(b"# coding: latin-1\nx = '\xc5\xbc'\n")
real_open, real_wrapper = io.open, io.TextIOWrapper
log = []


def logging_open(*args, **kwds):
    log.append(("open", [a if isinstance(a, str) else type(a).__name__ for a in args], sorted(kwds)))
    return real_open(*args, **kwds)


def logging_wrapper(*args, **kwds):
    log.append(("TextIOWrapper", [a if isinstance(a, str) else type(a).__name__ for a in args], sorted(kwds)))
    return real_wrapper(*args, **kwds)


class Lines:
    def __init__(self, lines, name="lines"):
        self.lines = list(lines)
        self.name = name

    def readline(self, *args):
        log.append((self.name + ".readline", args))
        return self.lines.pop(0) if self.lines else ""

    def close(self):
        log.append((self.name + ".close",))


def report(label, name, lineno):
    log.clear()
    print(label, ascii(shown(name, lineno)), log)


io.open = logging_open
report("a logged open:", "plain", 2)
report("a logged open, a missing file:", "nowhere/plain", 1)
io.TextIOWrapper = logging_wrapper
report("both logged:", "plain", 2)
io.open = real_open
io.TextIOWrapper = lambda binary, encoding: Lines(["one\n", "  two\n", "three"])
report("lines of the program's own:", "plain", 2)
report("its last line:", "plain", 3)
report("past its end:", "plain", 4)
io.TextIOWrapper = lambda binary, encoding: Lines([b"bytes\n", 5])
report("a line that is bytes:", "plain", 1)
report("a line that is no text:", "plain", 2)
io.TextIOWrapper = lambda binary, encoding: 1 / 0
report("a wrapper that fails:", "plain", 1)
io.TextIOWrapper = real_wrapper
io.open = lambda *args: 1 / 0
report("an open that fails:", "plain", 1)
io.open = lambda *args: 5
report("an open that answers an int:", "plain", 1)
io.open = lambda *args: -5
report("a negative one:", "plain", 1)
io.open = lambda *args: "text"
report("a str:", "plain", 1)
del io.open
report("no open:", "plain", 1)
io.open = real_open
del io.TextIOWrapper
report("no TextIOWrapper:", "plain", 1)
io.TextIOWrapper = real_wrapper
report("a spec, as they were:", "spec", 2)
sys.modules["io"] = None
report("io that cannot be imported:", "plain", 1)
sys.modules["io"] = io
report("and back:", "plain", 1)
del sys.modules["io"]
report("io imported again:", "plain", 1)
print("the same module:", sys.modules["io"] is io)
"""

# show_warning: a write for each part, and the first that fails ends it, whatever it raised
WRITES = HEAD + r"""
with open("plain", "wb") as out:
    out.write(b"first = 1\n    second = 2\n")
print(shown("plain", 2, whole=True))


class Failing:
    def __init__(self, at, what):
        self.at, self.what, self.written = at, what, []

    def write(self, text):
        if len(self.written) == self.at:
            raise self.what
        self.written.append(text)


class Named(UserWarning):
    pass


class Text:
    def __init__(self, answer):
        self.answer = answer

    def __str__(self):
        if isinstance(self.answer, BaseException):
            raise self.answer
        return self.answer


for at in range(10):
    for what in (ValueError("v"), OSError(5, "io"), KeyboardInterrupt(), SystemExit(3), GeneratorExit()):
        sys.stderr = catcher = Failing(at, what)
        try:
            _warnings.warn_explicit("m", Named, "plain", 2)
            outcome = "returned"
        except BaseException as raised:
            outcome = type(raised).__name__
        sys.stderr = sys.__stderr__
        print(at, type(what).__name__, outcome, catcher.written)
for label, stream in (("None", None), ("an object without write", object()), ("a write that is no callable", type("W", (), {"write": 5})())):
    sys.stderr = stream
    try:
        _warnings.warn_explicit("m", Named, "plain", 2)
        outcome = "returned"
    except BaseException as raised:
        outcome = type(raised).__name__
    sys.stderr = sys.__stderr__
    print(label, outcome)
for label, name in (("a str subclass", type("S", (str,), {})("plain")), ("one with a __str__", type("S", (str,), {"__str__": lambda self: "shown"})("plain"))):
    print(label, shown(name, 2, whole=True))
for label, text in (("a text of its own", Text("said")), ("a text that fails", Text(ValueError("no text")))):
    sys.stderr = catcher = Pieces()
    try:
        _warnings.warn_explicit(Named(text), None, "plain", 2)
        outcome = "returned"
    except BaseException as raised:
        outcome = type(raised).__name__
    sys.stderr = sys.__stderr__
    print(label, outcome, catcher.written)
Named.__name__ = "Renamed"
print(shown("plain", 1, whole=True))
"""

# The runtime's own import of `warnings` and of `io` is the only one that does not find a module the program does not hold:
# the program's own still stops by name, before a warning was printed and after
STOPS = (                                        # the name is put together when the program runs: the build links what a literal names
    ("print('start')\n__import__('warn' + 'ings')\n", "importing 'warnings'"),
    ("print('start')\nflag = True\n~flag\n__import__('warn' + 'ings')\n", "importing 'warnings'"),
    ("print('start')\nflag = True\n~flag\n__import__('i' + 'o')\n", "importing 'io'"),
    ("print('start')\nflag = True\n~flag\n__import__('line' + 'cache')\n", "importing 'linecache'"),
)
REPLACED_AFTER_A_FAILURE = HEAD + r"""
import io

with open("spec", "wb") as out:
    out.write(b"# coding: latin-1\n)\n")
real = io.TextIOWrapper
io.TextIOWrapper = lambda *args: real(*args)
print("start")
shown("spec", 1)
"""


def _stops(source: str, words: str) -> None:
    if shutil.which("g++") is None:
        return
    with tempfile.TemporaryDirectory() as tmp:
        prog = Path(tmp, "prog.py")
        prog.write_text(source, encoding="utf-8")
        got = subprocess.run([str(build(prog, "prog.py"))], capture_output=True, text=True, check=False, cwd=tmp)
    assert (got.returncode, got.stdout) == (70, "start\n") and words in got.stderr, got


def test_the_source_line_of_files_of_every_shape() -> None:
    """The line is decoded as the tokenizer's reading of the file's first lines says: a UTF-8 mark, a coding spec on the first
    line or on the second after an empty line or a comment, the spellings of utf-8 and latin-1, a spec the file's own bytes
    contradict, line ends of every kind, a NUL, lines longer than the reader's block; and no line at all where the tokenizer
    found an encoding and then failed (a spec against the mark, a NUL, a first token that is none)."""
    same({"main.py": FILES})


def test_where_the_file_is_looked_for() -> None:
    """By the name as given, then by its last part in sys.path's directories: entries that are no str, hold a NUL or are too
    long are passed over, a sys.path that is no list or is gone ends the search, a name with a NUL is cut there."""
    same({"main.py": WHERE})


def test_an_io_whose_functions_the_program_replaced() -> None:
    """io.open and io.TextIOWrapper are read from the module at each use and called as the C calls them; a line that is bytes or
    no text, a function that fails or is missing, a file object that is an int, and an io that cannot be imported print no
    line."""
    same({"main.py": REPLACED})


def test_the_writes_and_what_goes_wrong_in_them() -> None:
    """A write for each part; the first that fails ends the printing and nothing comes out of the call, whatever was raised;
    a sys.stderr that is None or cannot write; the file name and the text through str(); the category by its __name__."""
    same({"main.py": WRITES})


def test_the_programs_own_import_still_stops() -> None:
    for source, words in STOPS:
        _stops(source, words)


def test_a_replaced_wrapper_after_the_tokenizer_failed_stops() -> None:
    """CPython calls io.TextIOWrapper with the tokenizer's error still set; the type's own call fails at once, and a function
    the program put there would run with it."""
    _stops(REPLACED_AFTER_A_FAILURE, "an io.TextIOWrapper the program replaced")


if __name__ == "__main__":
    for name, value in sorted(globals().items()):
        if name.startswith("test_") and callable(value):
            value()
    print("ok")
