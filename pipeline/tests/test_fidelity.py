"""A build's fidelity (pipeline/build.py, FIDELITIES): what separates an exact build from a lean one, pinned without
building anything, and the helper for a program built both ways. The first seven tests need no compiler beyond what
`to_cpp` already asks (`header_macros()`); the last one builds.

What lean changes for a running program (deviation D-24: no look in generated code, no default SIGINT handler, a
handler's frame is None) is pinned by the signal tests (pipeline/tests/test_signals.py, which build with `_two`); here is
only the build's side."""
from __future__ import annotations

import contextlib
import importlib.util
import inspect
import io
import os
import re
import shutil
import subprocess
import sys
import tempfile
import textwrap
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import pipeline.build as build_module
from pipeline.backend.cpp import cpp_name
from pipeline.build import build, to_cpp
from pipeline.closed_world import namespace_of

ROOT = Path(build_module.__file__).resolve().parents[1]
INCLUDE = ROOT / "runtime" / "include"
RUNTIME_SOURCES = ROOT / "runtime" / "src"
MACRO = re.compile(r"\bBELLA_(?:LEAN|IS_LEAN|LOOK)\b")


def both_ways(src: str, argv: Sequence[str] = (), **run: Any) -> dict[str, subprocess.CompletedProcess[str]]:
    """The program under CPython ("cpython"), compiled exact ("exact") and compiled lean ("lean"), each run once from the
    program's directory; `run` goes to subprocess.run (stdin, env, preexec_fn, timeout). One source file, two builds: the
    runtime library, the prelude and the lowered texts are shared, the units are compiled once for each, and both
    binaries stay (the note of a program's last build is per fidelity)."""
    with tempfile.TemporaryDirectory() as tmp:
        prog = Path(tmp, "prog.py")
        prog.write_text(textwrap.dedent(src), encoding="utf-8")
        exact = build(prog, "prog.py")
        lean = build(prog, "prog.py", fidelity="lean")
        assert exact != lean and exact.exists() and lean.exists(), (exact, lean)
        commands = {"cpython": [sys.executable, str(prog)], "exact": [str(exact)], "lean": [str(lean)]}
        return {name: subprocess.run([*cmd, *argv], capture_output=True, text=True, check=False, cwd=tmp, **run)
                for name, cmd in commands.items()}


def test_what_separates_a_lean_build_is_in_its_keys() -> None:
    """Design point 3: the define reaches the units build() compiles and their keys; the runtime library, the prelude and
    the lowered text know no fidelity; a program has a binary and a note of its last build for each."""
    for flags in (build_module.PROGRAM_FLAGS, build_module.LIBRARY_FLAGS):
        lean = build_module._unit_flags(flags, "lean")
        assert lean == [*flags, "-DBELLA_LEAN"] and build_module._unit_flags(flags, "exact") is flags
        assert build_module._object_key("int x;\n", "g++", "c++26", lean) != build_module._object_key("int x;\n", "g++", "c++26", flags)
    for unaware in (build_module.runtime_library, build_module._runtime_key, build_module.lowered_unit, build_module.to_cpp,
                    build_module.main_unit):
        assert "fidelity" not in inspect.signature(unaware).parameters, unaware.__name__
    assert not any("BELLA_LEAN" in f for f in [*build_module.RUNTIME_FLAGS, *build_module.PRELUDE_FLAGS, *build_module.VENDORED_FLAGS])
    objs, lib = [Path("prog-0123456789abcdef.o")], Path("runtime-0123456789abcdef", "libbella.a")
    assert build_module._link_key(objs, lib, [], "exact") != build_module._link_key(objs, lib, [], "lean")
    program = Path(tempfile.gettempdir(), "no-such-program.py")
    assert build_module._pointer(program, "exact") != build_module._pointer(program, "lean")
    assert build_module._pointer(program, "exact").name == build_module._key(str(program.resolve()).encode())   # where it was
    try:
        build(program, "no-such-program.py", fidelity="fast")
    except ValueError as exc:
        assert "exact or lean" in str(exc)
    else:
        raise AssertionError("a fidelity that is neither was built")


def test_the_main_unit_says_which_build_it_is_by_one_text() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        prog = Path(tmp, "prog.py")
        prog.write_text("print(1)\n", encoding="utf-8")
        text = build_module.main_unit(prog, [])
    assert "    ::bella::set_lean(BELLA_IS_LEAN);\n    return ::bella::run_main(" in text, text[-400:]


def test_the_command_line_names_the_build() -> None:
    """--fidelity, then BELLA_FIDELITY, then exact; under --run what follows the program is the program's; a value that is
    neither stops with status 2 and builds nothing."""
    asked: list[str] = []
    ran: list[list[str]] = []
    saved = (build_module.build, os.execv, os.environ.get("BELLA_FIDELITY"))
    with tempfile.TemporaryDirectory() as tmp:
        fake = Path(tmp, "binary")
        fake.write_bytes(b"")

        def fake_build(program: Path, filename: str, *, notes: bool = True, fidelity: str = "exact") -> Path:
            asked.append(fidelity)
            return fake

        def outcome(argv: list[str], env: str | None) -> tuple[int | None, list[str], list[list[str]]]:
            del asked[:], ran[:]
            os.environ.pop("BELLA_FIDELITY", None)
            if env is not None:
                os.environ["BELLA_FIDELITY"] = env
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                return build_module.main(argv), list(asked), list(ran)

        def fake_execv(path: object, argv: Sequence[object]) -> None:
            ran.append([str(a) for a in argv])

        build_module.build = fake_build              # type: ignore[assignment]
        os.execv = fake_execv                        # type: ignore[assignment]
        try:
            assert outcome(["p.py"], None) == (0, ["exact"], [])
            assert outcome(["p.py"], "") == (0, ["exact"], [])
            assert outcome(["p.py"], "lean") == (0, ["lean"], [])
            assert outcome(["--fidelity=exact", "p.py"], "lean") == (0, ["exact"], [])
            assert outcome(["--fidelity", "lean", "p.py"], None) == (0, ["lean"], [])
            assert outcome(["p.py", "-o", str(Path(tmp, "out")), "--fidelity=lean"], None) == (0, ["lean"], [])
            assert outcome(["--run", "p.py", "a"], "lean") == (None, ["lean"], [["p.py", "a"]])
            assert outcome(["--fidelity=lean", "--run", "p.py"], None) == (None, ["lean"], [["p.py"]])
            assert outcome(["--run", "--fidelity=lean", "p.py", "--fidelity=exact"], None) == (None, ["lean"], [["p.py", "--fidelity=exact"]])
            assert outcome(["--run", "p.py", "--fidelity=lean"], None) == (None, ["exact"], [["p.py", "--fidelity=lean"]])
            for argv, env in ((["--fidelity=fast", "p.py"], None), (["p.py", "--fidelity"], None), (["p.py"], "LEAN"), (["--run", "p.py"], "fast")):
                assert outcome(argv, env) == (2, [], []), (argv, env)
        finally:
            build_module.build, os.execv = saved[0], saved[1]
            os.environ.pop("BELLA_FIDELITY", None)
            if saved[2] is not None:
                os.environ["BELLA_FIDELITY"] = saved[2]


NAMES = '''
import BELLA_LEAN
BELLA_LOOK = 1
def BELLA_IS_LEAN(BELLA_LEAN, *BELLA_LOOK, BELLA_IS_LEAN=2):
    BELLA_IS_LEAN = BELLA_LEAN
    def inner():
        nonlocal BELLA_IS_LEAN
        BELLA_IS_LEAN += 1
        return BELLA_IS_LEAN
    for BELLA_LOOK in range(3):
        pass
    try:
        pass
    except Exception as BELLA_LEAN:
        pass
    return [BELLA_LEAN for BELLA_LEAN in ()], inner, (lambda BELLA_LOOK: BELLA_LOOK)
class BELLA_LEAN:
    BELLA_LOOK = 3
    def BELLA_IS_LEAN(self, BELLA_LOOK):
        return self.BELLA_LEAN(BELLA_LOOK=BELLA_LOOK)
def gen(BELLA_LOOK):
    BELLA_LEAN = yield BELLA_LOOK
    yield BELLA_LEAN
def loops(BELLA_LOOK):
    for BELLA_LEAN in BELLA_LOOK:
        if BELLA_LEAN:
            continue
        BELLA_LOOK()
    while BELLA_LOOK:
        BELLA_LOOK = BELLA_LOOK()
'''


def _code(line: str) -> str:
    """A line of C++ as its tokens outside string literals and `//` comments, one blank between them."""
    return " ".join(re.sub(r'"(?:[^"\\]|\\.)*"', '""', line).split("//", 1)[0].split())


def bare_macro_names(text: str) -> list[str]:
    """The lines of a unit in which one of the three stands as a token of its own, outside string literals and comments.
    The emitter's own use of the macro is `BELLA_LOOK()` with its parentheses, wherever it stands (a statement, a
    statement under a `continue`'s label, a for statement's third expression) and is taken out first: no name of a
    program's reaches the text followed by `()`."""
    return [line for line in text.splitlines() if MACRO.search(re.sub(r"\bBELLA_LOOK\(\)", "", _code(line)))]


def test_the_macros_names_are_never_a_programs_identifier() -> None:
    """BELLA_LEAN is a macro only on a lean unit's command line, which `header_macros()` does not see: a local of that name
    would compile exact and not lean. The three are escaped as keywords are, whatever the compiler lists."""
    assert [cpp_name(n) for n in ("BELLA_LEAN", "BELLA_LOOK", "BELLA_IS_LEAN", "BELLA_LEANER")] == [
        "pyBELLA_1LEAN", "pyBELLA_1LOOK", "pyBELLA_1IS_1LEAN", "BELLA_LEANER"]
    assert bare_macro_names(to_cpp(NAMES, "names.py", "bella::m_main")) == []
    assert namespace_of("BELLA_LEAN") == "bella::mod_BELLA_1LEAN"


# The one place a header may ask whether the define is there, whole. The lean branch may take the define back (`#undef`), so
# that it goes no further than the header; what BELLA_LOOK() is in an exact unit is the header's to say, on one line.
LEAN_BLOCK = re.compile(r"(?m)^#ifdef BELLA_LEAN\n"
                        r"(?:#undef BELLA_LEAN\n)?"
                        r"#define BELLA_IS_LEAN 1\n"
                        r"#define BELLA_LOOK\(\)(?: \(\(void\)0\))?\n"
                        r"#else\n"
                        r"#define BELLA_IS_LEAN 0\n"
                        r"#define BELLA_LOOK\(\) ([^\n]*[^\n\\])\n"
                        r"#endif\n")


def lean_blocks(include: Path) -> list[str]:
    """What BELLA_LOOK() is in an exact unit, once for each time the headers under `include` branch on the define. Each
    time it must be LEAN_BLOCK and nothing more (anything else between its `#ifdef` and its `#endif` leaves the `#ifdef`
    standing), and outside it no line of a header may name one of the three: an AssertionError says which header and
    which lines."""
    looks: list[str] = []
    for header in sorted(f for f in include.rglob("*") if f.is_file()):
        lines = [re.sub(r"^# ", "#", _code(line)) for line in header.read_text(encoding="utf-8").splitlines()]
        text = "".join(line + "\n" for line in lines if line)
        looks += LEAN_BLOCK.findall(text)
        stray = [line for line in LEAN_BLOCK.sub("", text).splitlines() if MACRO.search(line)]
        assert not stray, (header.name, stray)
    return looks


def _one_expression(text: str) -> bool:
    """Whether a macro's body is one parenthesised expression: its first parenthesis closes at its last character."""
    depth = 0
    for i, c in enumerate(text):
        depth += (c == "(") - (c == ")")
        if depth == 0:
            return text.startswith("(") and i == len(text) - 1
    return False


def test_only_one_block_of_the_headers_knows_the_define() -> None:
    """The runtime library and the prelude are compiled once, without the define, and linked into both builds. So in the
    headers the define may choose the two macros' definitions and nothing else: an inline function, a constant or a second
    macro that differed would be two definitions of one name, of which the linker keeps either, and no build or test
    fails. The headers therefore hold the block once, exactly, and name the three nowhere else (both macros are defined
    either way: the emitter escapes what the compiler lists with no define). The runtime's own sources never ask the
    macros: there BELLA_IS_LEAN is 0 in a lean program too; they ask what the main unit told the runtime (set_lean).
    Until runtime.hpp has the block this fails: it lands with the header."""
    assert len(lean_blocks(INCLUDE)) == 1
    for source in sorted(RUNTIME_SOURCES.rglob("*")):
        if source.suffix in (".cpp", ".inc", ".hpp", ".h"):
            for n, line in enumerate(source.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
                assert not re.search(r"\bBELLA_(?:LEAN|IS_LEAN)\b", _code(line)), (source.name, n, line)


def test_the_headers_look_stands_where_the_emitter_writes_it() -> None:
    """Where the emitter writes the look other than as a statement of its own (`BELLA_LOOK();`, or one under a label),
    as a for statement's third clause (`for (;; BELLA_LOOK())`), the exact definition must be an expression: an `if`
    statement there would compile in a lean unit, where the macro is empty, and in no exact one. Decided from the text
    the emitter writes for loops with and without `continue`, so it holds whichever form of the loop look is taken.
    Until runtime.hpp has the block this fails: it lands with the header."""
    looks = lean_blocks(INCLUDE)
    assert len(looks) == 1, looks
    elsewhere = [line.strip() for line in to_cpp(NAMES, "names.py", "bella::m_main").splitlines()
                 if "BELLA_LOOK()" in _code(line) and not re.fullmatch(r"(?:\w+ ?: ?)?BELLA_LOOK\(\) ?;", _code(line))]
    assert not elsewhere or _one_expression(looks[0]), (looks[0], elsewhere[:2])


def test_a_lean_run_does_not_write_the_baseline() -> None:
    """tools/eval1_corpus.py --level c builds what BELLA_FIDELITY says; its baseline is the exact build's (guard.diff)."""
    spec = importlib.util.spec_from_file_location("eval1_corpus", ROOT / "tools" / "eval1_corpus.py")
    assert spec is not None and spec.loader is not None
    tool: Any = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(tool)
    ran: list[object] = []

    def fake_run(level: int | str = 1) -> dict[str, bool]:
        ran.append(level)
        return {}

    tool.run = fake_run
    before = tool.baseline_path("c").read_text(encoding="utf-8") if tool.baseline_path("c").exists() else None
    saved = os.environ.get("BELLA_FIDELITY")
    try:
        for value in ("lean", "fast"):
            os.environ["BELLA_FIDELITY"] = value
            with contextlib.redirect_stdout(io.StringIO()) as out:
                assert tool.main(["--level", "c", "--update"]) == 2
            assert not ran and ("unchanged" in out.getvalue() or "nothing was run" in out.getvalue()), out.getvalue()
    finally:
        os.environ.pop("BELLA_FIDELITY", None)
        if saved is not None:
            os.environ["BELLA_FIDELITY"] = saved
    assert (tool.baseline_path("c").read_text(encoding="utf-8") if tool.baseline_path("c").exists() else None) == before


def test_one_program_built_both_ways_keeps_both_binaries() -> None:
    """Needs the compiler. The two builds of a program that has nothing to do with signals print the same."""
    if shutil.which("g++") is None:
        return
    runs = both_ways("import os\nprint(sum(i * i for i in range(10)), os.sep)\n")
    assert {(r.stdout, r.returncode) for r in runs.values()} == {("285 /\n", 0)}, runs


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)
