# clause: C-8-19
# spec: section 8 (Environment)
# status: P1
# source: Python/pythonrun.c (pyrun_file), Parser/string_parser.c (warn_invalid_escape_sequence), Parser/lexer/lexer.c
#         (verify_end_of_number, the f-string's "\{"), Python/codegen.c (codegen_check_compare, codegen_assert, check_caller,
#         check_subscripter, check_index), Python/compile.c (_PyCompile_Warn, c_disable_warning), Python/errors.c
#         (_PyErr_EmitSyntaxWarning), Python/_warnings.c (warn_explicit, call_show_warning), Lib/_py_warnings.py
#         (_showwarnmsg_impl, _formatwarnmsg_impl)
"""CPython compiles a main program at each start, and its compiler warns each time of what it finds doubtful in the
text: an escape sequence that is none, a number that runs into a keyword, `is` with a literal, an assertion of a tuple,
a literal called or subscripted. Each is a SyntaxWarning given through the warnings machinery before the program's first
statement: the parser's in the order of the text, then the code generator's, each with the file, the line and the line's
text. A literal past the limit of digits ends the start where the parser meets it, after the warnings given until then.
The program starts itself again and prints what the second one wrote."""
# ruff: noqa: E501, F632, W605
import sys

EARLY = ("warnings" in sys.modules, "linecache" in sys.modules)   # at the first statement after `import sys`

import os  # noqa: E402

SHOW = "BELLA_CASE_SHOW"
value: object = 0
row = [1, 2, 3]
DIGITS = "\d+"                                   # the parser's: an escape sequence that is none
OCTAL = "\777"
RAW = b"\w"
FIELD = f"\d{value}"
BRACE = f"\{value}"
SPLIT = """a text of three lines,
the second with \q in it,
and the third"""
HALF = 1if value else 2                          # the tokenizer's: a number that runs into a keyword
if value is "":                                  # the code generator's, which come after all of the parser's
    pass
if value is not 1:
    pass
LIMIT = 9999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999
AFTER = "\s"                                     # below the long literal: not reached when that one is refused
PICKED = [n for n in row if n is 2]


def never_called() -> None:
    assert (value, "a tuple is always true")  # type: ignore[misc]  # noqa: F631
    (1, 2)(3)  # type: ignore[operator]
    1.5[0]  # type: ignore[index]
    "text"["key"]  # type: ignore[index]
    try:
        pass
    finally:
        if value is ():                          # a finally block's code is generated twice and warned of once
            pass


class Holder:
    def method(self) -> bool:
        return (lambda: value is 0)()


def show() -> None:
    cached = vars(sys.modules["linecache"])["cache"] if "linecache" in sys.modules else {}
    print("the program ran:", len(DIGITS), len(OCTAL), len(RAW), FIELD, BRACE, len(SPLIT), HALF, len(AFTER), PICKED, LIMIT.bit_length(),
          Holder().method())
    print("at its first statement: warnings imported", EARLY[0], "| linecache imported", EARLY[1], "| the program's lines cached",
          __file__ in cached, "| a registry among its globals", "__warningregistry__" in globals())


def again(error_closed: bool = False, **setting: str) -> None:
    """Start this program again with both outputs in one pipe; print its status and what it wrote."""
    here, there = os.pipe()
    error = (os.POSIX_SPAWN_CLOSE, 2) if error_closed else (os.POSIX_SPAWN_DUP2, there, 2)
    child = os.posix_spawn(sys.executable, sys.orig_argv, {"PYTHONHASHSEED": "0", SHOW: "yes"} | setting,
                           file_actions=[(os.POSIX_SPAWN_OPEN, 0, "/dev/null", os.O_RDONLY, 0), (os.POSIX_SPAWN_DUP2, there, 1),
                                         error, (os.POSIX_SPAWN_CLOSE, here)])
    os.close(there)
    wrote = b""
    while chunk := os.read(here, 65536):
        wrote += chunk
    os.close(here)
    status = os.waitstatus_to_exitcode(os.waitpid(child, 0)[1])
    print(", ".join(f"{name}={value!r}" for name, value in setting.items()) or "not set", "-> status", status)
    for line in wrote.decode().splitlines():
        if line.startswith(__file__ + ":"):                  # a warning names the program's own file, wherever it is
            line = os.path.basename(__file__) + line[len(__file__):]
        elif line.startswith("  File "):
            line = '  File "' + line[line.rindex(os.sep) + 1:]
        elif len(line) > 200:                                # the line of the long literal and the SyntaxError's own: start, length, end
            line = f"{line[:24]} ... ({len(line)} characters) ... {line[-12:]}"
        print("   ", line)


def main() -> None:
    again()
    print("---- the long literal is refused: the warnings the parser gave until then, and the SyntaxError")
    again(PYTHONINTMAXSTRDIGITS="640")
    again(PYTHONINTMAXSTRDIGITS="700")
    print("---- with standard error closed there is nowhere to write them")
    again(error_closed=True)


if SHOW in os.environ:
    show()
else:
    main()
