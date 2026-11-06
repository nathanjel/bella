# clause: C-6-18
# spec: section 6
# status: P1
# source: dialect specification section 6, Objects/exceptions.c
"""The exceptions that have fields of their own, and the rest of the hierarchy: OSError picks its subclass by errno, keeps two
of its arguments in args when a file name is given, and tells its __init__ from a subclass's; SyntaxError unpacks its second
argument; and each class has its place and its aliases."""
# ruff: noqa: ANN001, ANN002, ANN003, ANN204, B018, B023, E721, E731, PLR0133, RUF015, UP004, UP024
import errno


def failed(f: object) -> str:
    try:
        f()  # type: ignore[operator]
    except Exception as exc:
        return type(exc).__name__
    return "no error"


NAMES = ["ArithmeticError", "AssertionError", "AttributeError", "BaseException", "BlockingIOError", "BrokenPipeError", "BufferError", "BytesWarning", "ChildProcessError", "ConnectionAbortedError", "ConnectionError", "ConnectionRefusedError", "ConnectionResetError", "DeprecationWarning", "EOFError", "EncodingWarning", "Exception", "FileExistsError", "FileNotFoundError", "FloatingPointError", "FutureWarning", "GeneratorExit", "ImportError", "ImportWarning", "IndentationError", "IndexError", "InterruptedError", "IsADirectoryError", "KeyError", "KeyboardInterrupt", "LookupError", "MemoryError", "ModuleNotFoundError", "NameError", "NotADirectoryError", "NotImplementedError", "OSError", "OverflowError", "PendingDeprecationWarning", "PermissionError", "ProcessLookupError", "PythonFinalizationError", "RecursionError", "ReferenceError", "ResourceWarning", "RuntimeError", "RuntimeWarning", "StopAsyncIteration", "StopIteration", "SyntaxError", "SyntaxWarning", "SystemError", "SystemExit", "TabError", "TimeoutError", "TypeError", "UnboundLocalError", "UnicodeDecodeError", "UnicodeEncodeError", "UnicodeError", "UnicodeTranslateError", "UnicodeWarning", "UserWarning", "ValueError", "Warning", "ZeroDivisionError", "_IncompleteInputError"]
import builtins  # noqa: E402

for name in NAMES:
    c = getattr(builtins, name)
    print(name, c.__name__, c.__qualname__, c.__module__, [k.__name__ for k in c.__mro__], c.__doc__, repr(c), issubclass(c, BaseException))
print(EnvironmentError is OSError, IOError is OSError, builtins.EnvironmentError is OSError, builtins.IOError is OSError)

# ---- OSError picks its subclass
for code, shown in ((errno.EAGAIN, "EAGAIN"), (errno.EALREADY, "EALREADY"), (errno.EINPROGRESS, "EINPROGRESS"), (errno.EWOULDBLOCK, "EWOULDBLOCK"), (errno.EPIPE, "EPIPE"), (errno.ESHUTDOWN, "ESHUTDOWN"), (errno.ECHILD, "ECHILD"), (errno.ECONNABORTED, "ECONNABORTED"), (errno.ECONNREFUSED, "ECONNREFUSED"), (errno.ECONNRESET, "ECONNRESET"), (errno.EEXIST, "EEXIST"), (errno.ENOENT, "ENOENT"), (errno.EISDIR, "EISDIR"), (errno.ENOTDIR, "ENOTDIR"), (errno.EINTR, "EINTR"), (errno.EACCES, "EACCES"), (errno.EPERM, "EPERM"), (errno.ESRCH, "ESRCH"), (errno.ETIMEDOUT, "ETIMEDOUT"), (errno.EINVAL, "EINVAL"), (0, "0"), (-1, "-1"), (99999, "99999"), (2**70, "big")):
    e = OSError(code, "text")
    print(shown, type(e).__name__, e.errno == code, e.strerror, e.filename, e.filename2, e.args == (code, "text"), str(e) == "[Errno " + str(code) + "] text")
print(type(OSError(True, "x")).__name__, type(OSError(2.0, "x")).__name__, type(OSError("2", "x")).__name__, type(OSError(None, "x")).__name__, type(FileExistsError(2, "x")).__name__, type(PermissionError(errno.ENOENT, "x")).__name__, type(OSError(2)).__name__)


class MyError(OSError):
    pass


class WithInit(OSError):
    def __init__(self, *a, **k):  # type: ignore[no-untyped-def]
        self.seen = (a, k)
        super().__init__(*a, **k)


class InitNoSuper(OSError):
    def __init__(self, *a, **k):  # type: ignore[no-untyped-def]
        self.seen = (a, k)


class WithNew(OSError):
    def __new__(cls, *a, **k):  # type: ignore[no-untyped-def]
        self = super().__new__(cls, *a)
        self.made = (a, k)  # type: ignore[attr-defined]
        return self


class Both(OSError):
    def __new__(cls, *a, **k):  # type: ignore[no-untyped-def]
        return super().__new__(cls, *a)

    def __init__(self, *a, **k):  # type: ignore[no-untyped-def]
        self.seen = (a, k)


print(type(MyError(2, "x")).__name__, MyError(2, "x").errno, str(MyError(2, "x")), type(WithInit(2, "x")).__name__, WithInit(2, "x").errno, WithInit(2, "x").seen, str(WithInit(2, "x")), InitNoSuper(2, "x").errno, InitNoSuper(2, "x").args, InitNoSuper(2, "x").seen, str(InitNoSuper(2, "x")), InitNoSuper(2, "x", k=1).seen, failed(lambda: WithInit(2, "x", k=1)), WithNew(2, "x").errno, WithNew(2, "x").made, failed(lambda: WithNew(2, "x", k=1)), Both(2, "x").errno, Both(2, "x").seen, str(Both(2, "x")), issubclass(MyError, OSError))  # type: ignore[attr-defined,no-untyped-call]

# ---- its arguments
for args in ((), (1,), ("a",), (1, 2), (1, "a"), ("a", "b"), (2, "a", "f"), (2, "a", None), (2, "a", "f", None), (2, "a", "f", 1), (2, "a", "f", None, "g"), (2, "a", None, None, "g"), (2, "a", "f", None, None), (2, "a", 5), (2, "a", b"f"), (2, "a", "f", None, "g", 6), (1, 2, 3, 4, 5, 6, 7)):
    e = OSError(*args)
    print(args, type(e).__name__, e.args, e.errno, e.strerror, e.filename, e.filename2, str(e), repr(e), e.__reduce__()[0].__name__, e.__reduce__()[1], len(e.__reduce__()), failed(lambda: e.characters_written))  # type: ignore[attr-defined,union-attr]
print(failed(lambda: OSError(x=1)), failed(lambda: OSError(1, x=1)), failed(lambda: MyError(x=1)), failed(lambda: OSError.__new__()), failed(lambda: OSError.__new__(1)), failed(lambda: OSError.__new__(int)), type(OSError.__new__(OSError, 2, "x")).__name__, type(OSError.__new__(MyError, 2, "x")).__name__, OSError.__new__(OSError).args, OSError.__new__(OSError, 1, 2).args, failed(lambda: OSError.__init__(1)), OSError.__init__(OSError()), failed(lambda: OSError.__str__(1)), failed(lambda: OSError.__reduce__(1)))  # type: ignore[arg-type,call-arg,func-returns-value,type-var]
e = OSError(2, "a", "f")
e.errno = 5
e.strerror = "b"
e.filename = "g"
e.filename2 = "h"
print(e.errno, e.strerror, e.filename, e.filename2, str(e), e.args, e.__reduce__()[1])
e.filename2 = None
print(str(e), e.__reduce__()[1])
e.filename = None
print(str(e), e.__reduce__()[1])
del e.errno, e.strerror
print(e.errno, e.strerror, str(e))
e.x = 1  # type: ignore[attr-defined]
print(e.__reduce__()[2:], e.__dict__)
print(str(OSError(None, None)), str(OSError(1, None)), str(OSError(None, "a")), str(OSError(None, None, "f")), str(OSError(None, "a", "f")), str(OSError(1, None, "f")), str(OSError(None, None, "f", None, "g")), str(OSError("x", "y")), str(OSError(1)), str(OSError()), repr(OSError(1, "a", "f")), repr(FileNotFoundError(2, "a", "f")))

# ---- BlockingIOError's third argument
b = BlockingIOError(11, "a", 5)
print(type(b).__name__, b.characters_written, b.filename, b.args, str(b))
b.characters_written = 9
print(b.characters_written)
del b.characters_written
print(failed(lambda: b.characters_written), failed(lambda: delattr(b, "characters_written")), failed(lambda: setattr(b, "characters_written", "a")), failed(lambda: BlockingIOError(11, "a", 2**70)), BlockingIOError(11, "a", "f").filename, BlockingIOError(11, "a", "f").args, BlockingIOError(11, "a", True).characters_written, BlockingIOError(11, "a", 1.5).filename if False else 0, failed(lambda: BlockingIOError(11, "a", 1.5)), type(OSError(11, "a", 5)).__name__, OSError(11, "a", 5).characters_written, OSError(1, "a", 5).filename, failed(lambda: OSError(1, "a", 5).characters_written), failed(lambda: MyError(11, "a", 5).characters_written), MyError(11, "a", 5).filename)  # type: ignore[attr-defined]
k = OSError(1, "a")
k.characters_written = 3  # type: ignore[attr-defined]
print(k.characters_written, BlockingIOError().args, failed(lambda: BlockingIOError().characters_written))  # type: ignore[attr-defined]

# ---- caught by what it is
for code in (errno.ENOENT, errno.EEXIST, errno.EPIPE):
    try:
        raise OSError(code, "m", "p")
    except FileNotFoundError as x:
        print("not found", x.filename)
    except ConnectionError as x:
        print("connection", type(x).__name__)
    except OSError as x:
        print("os", type(x).__name__)
try:
    raise IOError(2, "m")
except EnvironmentError as x:
    print(type(x).__name__, isinstance(x, IOError))

# ---- SyntaxError
for args in ((), ("m",), (None,), (1,), ("m", ("f", 1, 2, "t")), ("m", ("f", 1, 2, "t", 3, 4)), ("m", ("f", 1, 2, "t", 3, 4, "meta")), ("m", ["f", 1, 2, "t"]), ("m", (None, None, None, None)), ("m", ("/a/b/c.py", 1, 2, "t")), ("m", ("c.py", "x", 2, "t")), ("m", (1, 1, 2, "t")), ("m", (None, 1, 2, "t")), ("m", ("f", None, 2, "t")), (1, 2, 3)):  # type: ignore[assignment]
    s = SyntaxError(*args)
    print(args, s.args, s.msg, s.filename, s.lineno, s.offset, s.text, s.end_lineno, s.end_offset, s.print_file_and_line, s._metadata, str(s), repr(s))  # type: ignore[attr-defined]
print(failed(lambda: SyntaxError("m", 1)), failed(lambda: SyntaxError("m", ())), failed(lambda: SyntaxError("m", (1, 2, 3))), failed(lambda: SyntaxError("m", (1, 2, 3, 4, 5))), failed(lambda: SyntaxError("m", (1, 2, 3, 4, 5, 6, 7, 8))), failed(lambda: SyntaxError(x=1)), failed(lambda: SyntaxError("m", None)), str(IndentationError("m", ("f", 1, 2, "t"))), str(TabError("t")), IndentationError("m").msg, TabError("m").msg, type(IndentationError("m")).__name__)  # type: ignore[arg-type,call-overload]
s = SyntaxError("m")
s.filename = "f"
s.lineno = 3
print(str(s))
s.lineno = 2**70
print(str(s))
s.lineno = True
print(str(s))
s.filename = 1  # type: ignore[assignment]
print(str(s))
s.lineno = "x"  # type: ignore[assignment]
print(str(s))
s.msg = 5  # type: ignore[assignment]
print(str(s))
del s.msg, s.filename, s.lineno
print(str(s), s.msg, s.filename, s.lineno)
s.print_file_and_line = 1  # type: ignore[assignment]
s._metadata = 2  # type: ignore[attr-defined]
print(s.print_file_and_line, s._metadata, failed(lambda: SyntaxError.__str__(1)), failed(lambda: SyntaxError.__init__(1)), SyntaxError.__init__(SyntaxError()))  # type: ignore[arg-type,attr-defined,call-overload]

# ---- the plain ones, and None's kind
print(repr(EOFError("a")), str(BufferError(1, 2)), Warning("w").args, UserWarning().args, issubclass(DeprecationWarning, Warning), issubclass(Warning, Exception), issubclass(TimeoutError, OSError), issubclass(StopAsyncIteration, Exception), failed(lambda: EOFError(x=1)), failed(lambda: Warning(x=1)), failed(lambda: type("X", (OSError, AttributeError), {})), failed(lambda: type("X", (OSError, SyntaxError), {})), failed(lambda: type("X", (OSError, ValueError), {})), type("X", (OSError, Exception), {}).__mro__[1].__name__, type("X", (ValueError, EOFError), {}).__mro__[1].__name__)  # type: ignore[call-arg]
print(type(None)() is None, type(NotImplemented)() is NotImplemented, type(...)() is ..., failed(lambda: type(None)(1)), failed(lambda: type(None)(x=1)), failed(lambda: type(NotImplemented)(1)), failed(lambda: type(...)(1)), type(None).__new__(type(None)) is None, failed(lambda: type(None).__new__(int)), failed(lambda: type(None).__new__()), failed(lambda: type("X", (type(None),), {})), failed(lambda: type("X", (type(...),), {})))  # type: ignore[call-arg,call-overload,misc]
