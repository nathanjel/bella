"""The exceptions with fields of their own, compiled, against CPython: the messages case C-6-18 does not compare."""
from __future__ import annotations

from pipeline.tests.test_review_2026_11_03 import same

MESSAGES = r"""
import errno
def show(f):
    try:
        print(repr(f()))
    except BaseException as e:
        print(type(e).__name__, e)
class MyError(OSError):
    pass
class WithInit(OSError):
    def __init__(self, *a, **k):
        super().__init__(*a, **k)
b = BlockingIOError(11, "a", 5)
s = SyntaxError("m")
for fn in (lambda: OSError(x=1), lambda: OSError(1, x=1), lambda: MyError(x=1), lambda: WithInit(2, "x", k=1), lambda: FileNotFoundError(x=1), lambda: OSError.__new__(), lambda: OSError.__new__(1), lambda: OSError.__new__(int), lambda: OSError.__init__(1), lambda: OSError.__init__(), lambda: OSError.__str__(1), lambda: OSError.__str__(OSError(), 1), lambda: OSError.__reduce__(1), lambda: OSError.__reduce__(OSError(), 1), lambda: OSError(1, "a").__reduce__(1),
           lambda: b.characters_written, lambda: setattr(b, "characters_written", "a"), lambda: setattr(b, "characters_written", 2**70), lambda: BlockingIOError(11, "a", 2**70), lambda: BlockingIOError(11, "a", 1.5), lambda: OSError(1, "a", 5).characters_written, lambda: delattr(OSError(), "characters_written"), lambda: OSError.__dict__["errno"].__get__(1), lambda: OSError.__dict__["errno"], lambda: OSError.__dict__["characters_written"], lambda: type(OSError.__dict__["errno"]).__name__, lambda: type(OSError.__dict__["characters_written"]).__name__, lambda: OSError.errno, lambda: OSError().nothing,
           lambda: OSError(2, "No such file", "/p"), lambda: OSError(2, "a", b"/p"), lambda: OSError(2, "a", 5), lambda: OSError(2, "a", "f", None, "g"), lambda: str(OSError(2, "a", "f", None, "g")), lambda: str(OSError(2, "a", b"f")), lambda: str(OSError(2, "a", 5)), lambda: str(OSError("x", "y", "f")), lambda: str(FileExistsError(17, "File exists", "/tmp/x")), lambda: repr(FileExistsError(17, "File exists", "/tmp/x")),
           lambda: SyntaxError("m", 1), lambda: SyntaxError("m", ()), lambda: SyntaxError("m", (1, 2, 3)), lambda: SyntaxError("m", (1, 2, 3, 4, 5)), lambda: SyntaxError("m", (1, 2, 3, 4, 5, 6, 7, 8)), lambda: SyntaxError(x=1), lambda: SyntaxError("m", None), lambda: SyntaxError.__str__(1), lambda: SyntaxError.__init__(1), lambda: SyntaxError.__dict__["msg"], lambda: type(SyntaxError.__dict__["msg"]).__name__, lambda: s.nothing, lambda: EOFError(x=1), lambda: Warning(x=1), lambda: type("X", (OSError, AttributeError), {}), lambda: type("X", (OSError, SyntaxError), {}), lambda: type("X", (StopIteration, OSError), {}),
           lambda: type(None)(1), lambda: type(None)(x=1), lambda: type(NotImplemented)(1), lambda: type(...)(1), lambda: type(None).__new__(int), lambda: type(None).__new__(), lambda: type(None).__new__(1), lambda: type("X", (type(None),), {}), lambda: type("X", (type(...),), {}), lambda: type("X", (type(NotImplemented),), {}),
           lambda: errno.ENOENT, lambda: errno.errorcode[2], lambda: errno.errorcode[errno.EAGAIN], lambda: errno.errorcode[errno.EWOULDBLOCK], lambda: errno.nothing, lambda: len(errno.errorcode), lambda: sorted([k for k in vars(errno) if k.startswith("E")]) == sorted(set(errno.errorcode.values())), lambda: errno.__name__, lambda: errno.__doc__[:10]):
    show(fn)
for code in (errno.ENOENT, errno.EEXIST, errno.EPIPE, errno.EAGAIN):
    try:
        raise OSError(code, "text", "path")
    except OSError as e:
        print(type(e).__name__, e, e.errno == code, repr(e))
def uncaught():
    raise FileNotFoundError(2, "No such file or directory", "/nothing")
try:
    uncaught()
except OSError as e:
    print(e.__traceback__ is not None, e.__traceback__.tb_lineno)
print(EnvironmentError.__name__, IOError.__name__, EnvironmentError is IOError)
"""


def test_messages() -> None:
    same(MESSAGES)


if __name__ == "__main__":
    test_messages()
