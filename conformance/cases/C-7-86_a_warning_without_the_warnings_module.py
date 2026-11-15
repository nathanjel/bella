# clause: C-7-86
# spec: section 7
# status: P1
# deviation: D-27
# source: Python/_warnings.c (get_warnings_attr: "Fallback to the C implementation if we cannot get the Python implementation";
#         show_warning), Python/traceback.c (display_source_line, _Py_FindSourceFile), Parser/tokenizer/helpers.c (the coding
#         spec of a file's first two lines), the author's decision of 2026-11-14 (a warning in a program without `warnings`)
"""A warning in a program that holds no `warnings` module. CPython imports `warnings` when the first warning is shown and
prints through it; a compiled program holds the modules its imports reach, and this one imports none written in Python, so
its warnings are printed as CPython's C prints them when that import fails: the file, the line, the category and the text,
and beneath them the source line, read from the file. For most warnings the two print the same (the rows up to "where
they part"); the rest is deviation D-27: the line as it stands but for the spaces, tabs and form feeds before it, a file
found by its name alone on sys.path, the text in pieces, and whatever goes wrong while writing
dropped. The second expectation is CPython with the import of `warnings` made to fail."""
# ruff: noqa: E101, E501, RUF001, W291  # the sample lines are what they are: a tab before, spaces after, a no-break space
import sys

import _io
import _warnings

SAMPLES = """
    indented by four spaces [s1]
	  a tab, a form feed and two spaces before [s2]
zażółć gęślą jaźń, and nothing before it [s3]

spaces after it [s5]   
a vertical tab before it [s6]
 a no-break space before it [s7]
"""
NAME = __file__.rpartition("/")[2]
PREFIX = __file__[:len(__file__) - len(NAME)]
with _io.open(__file__, encoding="utf-8") as handle:
    SOURCE = handle.read().split("\n")


class Mine(UserWarning):
    """A category of the program's own: shown wherever it is raised, every time when no registry is given."""


class Pieces:
    """What stands in for sys.stderr: each write as it came. With a limit, the write after that many fails."""

    def __init__(self, limit: int = -1) -> None:
        self.written: list[str] = []
        self.limit = limit

    def write(self, text: str) -> int:
        if len(self.written) == self.limit:
            raise ValueError("no more")
        self.written.append(text)
        return len(text)


def line_of(key: str) -> int:
    tag = "[" + key + "]"
    return [number for number, line in enumerate(SOURCE, 1) if tag in line][0]


def take() -> str:
    """What was written since the last call, the directory of this file left out."""
    text = "".join(catcher.written)
    catcher.written.clear()
    return text.replace(PREFIX, "") if PREFIX else text


def invert(flag: bool) -> int:
    return ~flag                             # the line the runtime's own warning is charged to


def nested() -> None:
    _warnings.warn("from a function", Mine)


def charged_to_the_caller() -> None:
    _warnings.warn("charged to the caller", Mine, 2)


real_stderr = sys.stderr
catcher = Pieces()
sys.stderr = catcher
try:
    print("the runtime's own:", [invert(True), invert(True), invert(False)], ascii(take()))
    _warnings.warn("at the top of the module")
    print("warn:", ascii(take()))
    nested()
    print("warn in a function:", ascii(take()))
    charged_to_the_caller()
    print("warn, a level up:", ascii(take()))
    _warnings.warn(Mine("an instance", 2))
    print("an instance:", ascii(take()))
    _warnings.warn_explicit("a category of CPython's", RuntimeWarning, __file__, line_of("s1"))
    print("another category:", ascii(take()))
    for key in ("s1", "s2", "s3"):
        _warnings.warn_explicit("the line " + key, Mine, __file__, line_of(key))
        print("a line of the file:", ascii(take()))
    _warnings.warn_explicit("an empty line", Mine, __file__, line_of("s3") + 1)
    print("an empty line:", ascii(take()))
    _warnings.warn_explicit("by the name alone", Mine, NAME, line_of("s1"))
    print("a name the working directory has:", ascii(take()))
    for number in (len(SOURCE) + 5, 0, -3):
        _warnings.warn_explicit("no such line", Mine, __file__, number)
        print("a line the file lacks:", ascii(take()))
    for name in ("nowhere.py", "<string>", "<a name in brackets>", "", "/", "nowhere/"):
        _warnings.warn_explicit("no such file", Mine, name, 1)
        print("a file that cannot be read:", ascii(take()))
    _warnings.warn_explicit("twice", Mine, __file__, line_of("s1"))
    _warnings.warn_explicit("twice", Mine, __file__, line_of("s1"))
    print("with no registry, every time:", take().count("twice"))
    registry: dict[str | tuple[str, type[Warning], int], int] = {}
    _warnings.warn_explicit("once", Mine, __file__, line_of("s1"), registry=registry)
    _warnings.warn_explicit("once", Mine, __file__, line_of("s1"), registry=registry)
    print("with a registry, once:", take().count("once"), len(registry))
    sys.stderr = None
    _warnings.warn_explicit("to nowhere", Mine, __file__, line_of("s1"))
    sys.stderr = catcher
    print("sys.stderr is None:", ascii(take()))

    # ---- where they part (D-27) ----
    for key in ("s5", "s6", "s7"):
        _warnings.warn_explicit("the line " + key, Mine, __file__, line_of(key))
        print("a line as it stands:", ascii(take()))
    _warnings.warn_explicit("found on sys.path", Mine, "nowhere/" + NAME, line_of("s1"))
    print("a name only sys.path has:", ascii(take()))
    _warnings.warn_explicit("in pieces", Mine, __file__, line_of("s1"))
    print("the writes:", [piece.replace(PREFIX, "") if PREFIX else piece for piece in catcher.written])
    take()
    for limit in (0, 2, 7):
        catcher = Pieces(limit)
        sys.stderr = catcher
        try:
            _warnings.warn_explicit("a write fails", Mine, __file__, line_of("s1"))
            outcome = "nothing came out of the call"
        except ValueError as failure:
            outcome = "ValueError came out of the call: " + str(failure.args)
        print("a write that fails:", outcome, "|", ascii(take()))
    print("the module afterwards:", sys.modules.get("warnings") is not None)
finally:
    sys.stderr = real_stderr
