"""Review A26 of 2026-11-21 (commit 369abde), compiled against CPython: a test for each finding fixed.

Codex's Astra at low effort read the step that gives the compiler's warnings of a main program's text at each start
(RL-572, C-8-19, D-29); the review log has its eleven findings as RL-601 to RL-611. Seven are fixed and held here, each
with the report's own reproduction and what stands beside it: the build's note before a refusal (RL-601), the limit of
digits changed while a warning is shown (RL-605, a stop that names itself), the name CPython has for a program started
by a path that is not normalised (RL-606), the note of a binary that two kinds of build share (RL-609), the encoding of
a text whose lines end in a carriage return alone (RL-610), and the warnings CPython gives when its parser refuses a
literal (RL-611). RL-608 is the harness's own (conformance/tests/test_harness.py). RL-602 and RL-603 are the build's
note as designed, RL-604 is the author's, RL-607 is open. RL-612 was in the reviewer's probes and not in its report: a
program outside the dialect ended the build's command with a traceback.

Run under pytest or directly: python3 -m pipeline.tests.test_review_2026_11_21_a26
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from pipeline import build as build_module
from pipeline.build import build, run_filename
from pipeline.closed_world import read_source
from pipeline.tests.test_start_up_environment import _plain_environment, _sides

BUILDER = [sys.executable, str(Path(build_module.__file__))]
WARNED = 'SyntaxWarning: "\\q" is an invalid escape sequence. Such sequences will not work in the future. Did you mean "\\\\q"? A raw string is also an option.'


def _command(args: list[str], cwd: str, **more: str) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(args, capture_output=True, check=False, env=_plain_environment() | more, cwd=cwd, stdin=subprocess.DEVNULL)


def test_the_builds_note_before_a_refusal() -> None:
    """RL-601: a text CPython's compiler refuses is not built, and the build says so with status 70. CPython's compiler
    gave its warnings until the error, and a build that only builds says them first; under --run the refusal alone."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp = str(Path(tmp).resolve())
        Path(tmp, "prog.py").write_text("a='\\q'\nif :\n pass\nb='\\w'\n", encoding="utf-8")
        reference = _command([sys.executable, "prog.py"], tmp)
        assert reference.returncode == 1 and reference.stderr.startswith(f"{tmp}/prog.py:1: {WARNED}\n  a='\\q'\n".encode()), reference
        assert b"\\w" not in reference.stderr                                  # the compiler never came to line 4
        built = _command([*BUILDER, "prog.py"], tmp)
        assert built.returncode == 70 and built.stdout == b"", built
        assert built.stderr.decode().splitlines() == [f"{tmp}/prog.py:1: {WARNED}", "  a='\\q'",
                                                      "bella: refused: invalid syntax (prog.py, line 2)"], built.stderr
        ran = _command([*BUILDER, "--run", "prog.py"], tmp)
        assert ran.returncode == 70 and ran.stderr.decode().splitlines() == ["bella: refused: invalid syntax (prog.py, line 2)"], ran


def test_a_program_outside_the_dialect_is_refused_by_the_command() -> None:
    """RL-612: `return` out of a finally block is a compile-time error of the dialect (D-10), which the passes raise as a
    DialectError. The evaluators' commands refuse it with status 70; the build's command let it through as a traceback
    with status 1. CPython warns of the line and runs the program, and a build that only builds says that warning too."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp = str(Path(tmp).resolve())
        Path(tmp, "prog.py").write_text("def f() -> int:\n    try:\n        pass\n    finally:\n        return 1\nprint(f())\n", encoding="utf-8")
        warned = [f"{tmp}/prog.py:5: SyntaxWarning: 'return' in a 'finally' block", "  return 1"]
        refusal = "bella: refused: D-10: 'return' leaving a finally block is a compile-time error (line 5)"
        reference = _command([sys.executable, "prog.py"], tmp)
        assert (reference.returncode, reference.stdout, reference.stderr.decode().splitlines()) == (0, b"1\n", warned), reference
        built = _command([*BUILDER, "prog.py"], tmp)
        assert (built.returncode, built.stdout, built.stderr.decode().splitlines()) == (70, b"", [*warned, refusal]), built
        ran = _command([*BUILDER, "--run", "prog.py"], tmp)
        assert (ran.returncode, ran.stdout, ran.stderr.decode().splitlines()) == (70, b"", [refusal]), ran


def test_the_limit_of_digits_changed_while_a_warning_is_shown() -> None:
    """RL-605: CPython reads the limit of digits when its parser meets each literal, and what shows a warning before that
    may change it: a warnings.py of the program's own, imported for the first warning. The start judges a literal by the
    limit it began with, so where the limit is another after a warning it stops by name; CPython's answers are held here
    so that the stop is known to be one. A text with no literal a limit can reach is not stopped."""
    if shutil.which("g++") is None:
        return
    nines = "9" * 641
    for limit, env, status, wrote in (("640", {}, 1, b""), ("0", {"PYTHONINTMAXSTRDIGITS": "640"}, 0, b"ran\n")):
        with tempfile.TemporaryDirectory() as tmp:
            prog = Path(tmp, "prog.py")
            prog.write_text(f"a='\\q'\nb={nines}\nprint('ran')\n", encoding="utf-8")
            Path(tmp, "warnings.py").write_text(f"import sys\nsys.set_int_max_str_digits({limit})\n", encoding="utf-8")
            exe = str(build(prog, "prog.py", notes=False))
            reference, compiled = _sides(exe, _plain_environment() | env, tmp)
            assert (reference[0], reference[1]) == (status, wrote) and (b"SyntaxError: Exceeds the limit" in reference[2]) == (status == 1), reference
            first = f"{prog}:1: {WARNED}\n".encode()
            assert reference[2].startswith(first), reference[2]                # the module has no _showwarnmsg: the C's own line, no source line
            assert compiled[0] == 70 and compiled[1] == b"" and compiled[2].startswith(first), compiled
            assert compiled[2].endswith(b"bella: not implemented: the limit of digits changed while the compiler's warnings of the main "
                                        b"program's text were given, and the text has a literal a limit can refuse\n"), compiled[2]
    with tempfile.TemporaryDirectory() as tmp:
        prog = Path(tmp, "prog.py")
        prog.write_text("import sys\na='\\q'\nb=" + "9" * 640 + "\nprint('ran', sys.get_int_max_str_digits())\n", encoding="utf-8")
        Path(tmp, "warnings.py").write_text("import sys\nsys.set_int_max_str_digits(640)\n", encoding="utf-8")
        reference, compiled = _sides(str(build(prog, "prog.py", notes=False)), _plain_environment(), tmp)
        assert compiled == reference and reference[:2] == (0, b"ran 640\n"), (compiled, reference)


def test_the_name_cpython_has_for_the_program() -> None:
    """RL-606: `python PATH` makes PATH absolute by putting the current directory before it and normalises nothing
    (_Py_abspath). That name is the main module's __file__, the name in its code objects and the file a warning names and
    reads: through a link to a directory, `link/../prog.py` is another file than the normalised name says."""
    assert run_filename("/a/./b/../c.py") == "/a/./b/../c.py" and run_filename("./c.py") == os.getcwd() + "/./c.py"
    if shutil.which("g++") is None:
        return
    with tempfile.TemporaryDirectory() as tmp:
        tmp = str(Path(tmp).resolve())
        Path(tmp, "actual", "sub").mkdir(parents=True)
        Path(tmp, "link").symlink_to("actual/sub")
        text = ("import sys\ndef where() -> str:\n    return where.__code__.co_filename\n"
                "print(__file__, sys.argv[0], sys.path[0], where() == __file__)\na='\\q'\nraise SystemExit(3)\n")
        Path(tmp, "actual", "prog.py").write_text(text, encoding="utf-8")
        Path(tmp, "prog.py").write_text("# another file\n# of other lines\n# and none of them the program's\n# here\n# unrelated fifth line\n", encoding="utf-8")
        Path(tmp, "dot.py").write_text(text, encoding="utf-8")
        for given, named in (("link/../prog.py", tmp + "/link/../prog.py"), ("./dot.py", tmp + "/./dot.py"), ("actual/../dot.py", tmp + "/actual/../dot.py"),
                             (".//dot.py", tmp + "/.//dot.py"), (tmp + "//dot.py", tmp + "//dot.py"), ("dot.py", tmp + "/dot.py")):
            reference = _command([sys.executable, given], tmp)
            compiled = _command([*BUILDER, "--run", given], tmp)
            assert (compiled.returncode, compiled.stdout, compiled.stderr) == (reference.returncode, reference.stdout, reference.stderr), (given, compiled, reference)
            directory = tmp + "/actual" if given.startswith("link") else tmp
            assert reference.returncode == 3 and reference.stdout.decode() == f"{named} {given} {directory} True\n", (given, reference.stdout)
            assert reference.stderr.decode() == f"{named}:5: {WARNED}\n  a='\\q'\n", (given, reference.stderr)


def test_two_kinds_of_build_that_share_a_binary() -> None:
    """RL-609: a program with nothing to warn of is one binary with and without --syntax-warnings. Each build notes it,
    and a rebuild of one kind leaves the binary the other kind's last build named."""
    if shutil.which("g++") is None:
        return
    with tempfile.TemporaryDirectory() as tmp:
        prog = Path(tmp, "prog.py")
        prog.write_text('print("plain")\n', encoding="utf-8")
        loud, quiet = build(prog, "prog.py", notes=False), build(prog, "prog.py", notes=False, syntax_warnings=False)
        assert loud == quiet and quiet.exists()
        notes = [build_module._pointer(prog, "exact", warns) for warns in (True, False)]
        assert [n.read_text(encoding="utf-8") for n in notes] == [loud.parent.name] * 2
        try:
            prog.write_text('print("plain")\na = "\\q"\n', encoding="utf-8")
            louder = build(prog, "prog.py", notes=False)
            assert louder != loud and louder.exists() and quiet.exists(), (louder, quiet)      # the other kind's binary stays
            assert subprocess.run([str(quiet)], capture_output=True, check=False).stdout == b"plain\n"
            quieter = build(prog, "prog.py", notes=False, syntax_warnings=False)
            assert quieter not in (louder, quiet) and quieter.exists() and louder.exists() and not quiet.exists()   # and goes with its own rebuild
        finally:
            for kept in {n.read_text(encoding="utf-8") for n in notes if n.exists()}:
                shutil.rmtree(build_module.BUILD / kept, ignore_errors=True)
            for n in notes:
                n.unlink(missing_ok=True)


def test_the_encoding_of_a_text_whose_lines_end_in_a_carriage_return() -> None:
    """RL-610: CPython's tokenizer looks for the coding cookie on the first two lines, and a carriage return alone ends a
    line. tokenize.detect_encoding, which the build asked through importlib.util.decode_source, reads lines by the line
    feed alone: a file of carriage returns that begins with a comment was one first line to it, and a cookie anywhere in
    the file decided the encoding, so a string of the program's had another value."""
    late = "# first\rx=0\r# coding: latin-1\ra='\u00e9'\rprint(a, ascii(a))\r".encode()
    texts = {
        "a cookie on line 3, carriage returns": (late, b"\xc3\xa9 '\\xe9'\n"),
        "a cookie on line 3, both": (late.replace(b"\r", b"\r\n"), b"\xc3\xa9 '\\xe9'\n"),
        "a cookie on line 2, carriage returns": ("# first\r# coding: latin-1\ra='\u00e9'\rprint(a, ascii(a))\r".encode("latin-1"), b"\xc3\xa9 '\\xe9'\n"),
        "a cookie on line 1, carriage returns": ("# coding: latin-1\ra='\u00e9'\rprint(a, ascii(a))\r".encode("latin-1"), b"\xc3\xa9 '\\xe9'\n"),
        "a cookie after a blank line": ("\r# coding: latin-1\ra='\u00e9'\rprint(a, ascii(a))\r".encode("latin-1"), b"\xc3\xa9 '\\xe9'\n"),
        "a cookie on line 3 after a form feed": ("\x0c# first\r\r# coding: latin-1\ra='\u00e9'\rprint(a, ascii(a))\r".encode(), b"\xc3\xa9 '\\xe9'\n"),
    }
    with tempfile.TemporaryDirectory() as tmp:
        for name, (text, wrote) in texts.items():
            Path(tmp, "prog.py").write_bytes(text)
            assert "\u00e9" in read_source(Path(tmp, "prog.py")) and "\r" not in read_source(Path(tmp, "prog.py")), name
            if shutil.which("g++") is None:
                continue
            reference, compiled = _sides(str(build(Path(tmp, "prog.py"), "prog.py", notes=False)), _plain_environment(), tmp)
            assert compiled == reference and reference == (0, wrote, b""), (name, compiled, reference)


def _nines(n: int) -> str:
    return "9" * n


# RL-611's class: what CPython gives when its parser refuses a literal is the warnings until then and, after them, the
# tokenizer's warnings of the rest of the text (a number that runs into a keyword, "\{" in an f-string), which it reads on
# to look for a tokenizer's error; the parser's (an escape in a string) and the code generator's of the rest are not given.
# Each limit refuses another literal: with the tokenizer's warnings before it, after it on its line and further down.
REFUSED = "\n".join([
    "x: object = 0",
    "a = " + "1_" * 640 + "1",                                      # 641 digits
    "b = '\\q'",
    "c = 1if x else 2",
    "d = f'\\{x}'",
    "e = (0x1for z in ()), " + _nines(650) + ", 1or x",
    "g = '\\w'; h = 1and x",
    "i = [" + _nines(660) + ", f'\\{x}\\d', 1.5if x else 0]",
    "if x is 1: pass",
    "j = " + _nines(670),
    "k = 1not in ()",
    "print('ran', c, h)",
    ""])


def test_what_cpython_warns_of_when_a_literal_is_refused() -> None:
    """RL-611: the warnings before the SyntaxError are the refused compile's own, noted for each literal a limit can
    reach, not the first so many of the whole compile's."""
    if shutil.which("g++") is None:
        return
    with tempfile.TemporaryDirectory() as tmp:
        prog = Path(tmp, "prog.py")
        prog.write_text(REFUSED, encoding="utf-8")
        exe = str(build(prog, "prog.py", notes=False))
        lines: dict[str, list[str]] = {}
        for limit in ("640", "641", "650", "660", "670"):
            reference, compiled = _sides(exe, _plain_environment() | {"PYTHONINTMAXSTRDIGITS": limit}, tmp)
            assert compiled == reference, (limit, compiled, reference)
            assert (reference[0] == 1) == (b"SyntaxError: Exceeds the limit" in reference[2]), (limit, reference)
            lines[limit] = [row.split(":")[1] for row in reference[2].decode().splitlines() if "SyntaxWarning: " in row]
        # the lines warned of: the tokenizer's of the whole rest where a literal is refused, every warning where none is
        assert lines == {"640": ["4", "5", "6", "6", "7", "8", "8", "11"], "641": ["3", "4", "5", "6", "6", "7", "8", "8", "11"],
                         "650": ["3", "4", "5", "6", "6", "7", "7", "8", "8", "11"],
                         "660": ["3", "4", "5", "6", "6", "7", "7", "8", "8", "8", "11"],
                         "670": ["3", "4", "5", "6", "6", "7", "7", "8", "8", "8", "11", "9"]}, lines


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)
