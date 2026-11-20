"""Reviews S22 and A22 of 2026-11-19 (range 3234866..bc3f700), compiled against CPython: one program for each finding fixed.

Nine Sonnet reviewers and Codex's Astra read the range since F21; the review log has their 79 findings as RL-454 to RL-521,
and RL-522 was found while a fix was checked. Each program here is a finding's own, or a lighter one that shows the same,
run under CPython and compiled: standard output, the exit status and standard error must agree, the last after the harness's
mask (D-06), without addresses and with file names cut to their last part. Findings that are left open or are the author's
to decide have no program here; the log says which.

Run under pytest or directly: python3 -m pipeline.tests.test_review_2026_11_19
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

from conformance.harness import mask_stderr
from pipeline.build import build

FINDINGS: list[tuple[str, str, str]] = [
    ('RL-454', "throw: the class's constructor closes the generator", r'''
import warnings
warnings.simplefilter("ignore")
def gen():
    yield 1
class E(Exception):
    def __init__(self): g.close()
g = gen()
next(g)
try: g.throw(E, None)
except BaseException as e: print(type(e).__name__)
'''),
    ('RL-454', 'throw: the constructor resumes it, and gi_running', r'''
class Advance(ValueError):
    def __init__(self, *a):
        try:
            next(gg)
        except BaseException as e:
            print("next in init ->", type(e).__name__, e)
def g4():
    try:
        yield 1
    except ValueError:
        print("g4 handler")
        yield "handled"
    yield "after handler"
gg = g4(); next(gg)
try:
    print("throw ->", gg.throw(Advance))
except BaseException as e:
    print("raised", type(e).__name__)
print("next ->", next(gg, "exhausted"))
'''),
    ('RL-455', "throw: the delegate's throw attribute raises", r'''
import warnings
warnings.simplefilter("ignore")
class Child:
    def __iter__(self): return self
    def __next__(self): return "child"
    @property
    def throw(self): raise LookupError("lookup")
def parent(child):
    try: yield from child
    except LookupError: yield "caught"
g = parent(Child())
next(g)
try: print(g.throw(ValueError, 1))
except LookupError: print("lookup escaped")
print(next(g, "ended"))
'''),
    ('RL-455', 'throw: the same, with the stack and the generator afterwards', r'''
import traceback
class BadThrow:
    def __iter__(self): return self
    def __next__(self): return 1
    @property
    def throw(self): raise RuntimeError("throw attr")
def deleg(x):
    yield from x
g = deleg(BadThrow()); next(g)
try:
    g.throw(ValueError("x"))
except RuntimeError as e:
    print([x.name for x in traceback.extract_tb(e.__traceback__)])
print(next(g, "exhausted"))
'''),
    ('RL-456', 'throw: the delegating generator is on the stack', r'''
import traceback, warnings
warnings.simplefilter("ignore")
class Child:
    def __iter__(self): return self
    def __next__(self): return "child"
    def throw(self, *args): return [f.name for f in traceback.extract_stack()]
def parent(child): yield from child
g = parent(Child())
next(g)
print(g.throw(ValueError, 1))
'''),
    ('RL-456', 'throw: the line of the inner warning', r'''
import warnings
class Wrap:
    def __init__(self, g): self.g = g
    def __iter__(self): return self
    def __next__(self): return next(self.g)
    @property
    def throw(self): return self.g.throw
def outer(x):
    yield from x          # line 10
def inner():
    try:
        yield 1
    except ValueError:
        yield 2
with warnings.catch_warnings(record=True) as caught:
    warnings.simplefilter("always")
    o = outer(Wrap(inner())); next(o)
    o.throw(ValueError, "w")   # line 19
print([w.lineno for w in caught])
'''),
    ('RL-457', 'struct: a BaseException from __float__ and __complex__', r'''
import struct
class Halt(BaseException): pass
class Bad:
    def __float__(self): raise Halt
    def __complex__(self): raise Halt
for fmt in ("d", "D"):
    try: struct.pack(fmt, Bad())
    except BaseException as e: print(type(e).__name__, str(e), e.__context__)
'''),
    ('RL-457', 'struct: SystemExit and KeyboardInterrupt', r'''
import struct

class Boom:
    def __float__(self):
        raise SystemExit("from __float__")

try:
    struct.pack("<d", Boom())
except BaseException as e:
    print(type(e).__name__, e.args)
'''),
    ('RL-457', 'struct: KeyboardInterrupt uncaught', r'''
import struct
class KI:
    def __float__(self): raise KeyboardInterrupt("k")
struct.pack("<d", KI())
'''),
    ('RL-457', "time: a KeyboardInterrupt from the clock id's __index__", r'''
import time
class Bad:
    def __index__(self): raise KeyboardInterrupt()
try: time.clock_gettime(Bad())
except BaseException as e: print(type(e).__name__)
'''),
    ('RL-458', 'complex: the temporary of __complex__ dies first', r'''
import warnings
warnings.simplefilter("ignore")
class Temp(complex):
    def __del__(self): print("released")
class Real:
    def __complex__(self): return Temp(1)
class Imag:
    def __float__(self):
        print("imag")
        return 0.
print(complex(Real(),Imag()))
'''),
    ('RL-459', 'clear_frames through the earlier traceback of a frame', r'''
import traceback
events = []
class Resource:
    def __del__(self): events.append("closed")
previous = []
def f():
    r = Resource()
    try: raise ValueError()
    except ValueError as e: previous.append(e.__traceback__)
    raise RuntimeError()
try: f()
except RuntimeError:
    traceback.clear_frames(previous[0])
    print(events)
'''),
    ('RL-460', "a class attribute named like the function's cell", r'''
def f():
    x = 4
    class C:
        x = 5
        def method(self): return x
    print(list(locals()), C().method())
print(f.__code__.co_cellvars, f.__code__.co_varnames)
f()
'''),
    ('RL-461', "the warning printer and a str subclass's __getitem__", r'''
import sys, _io, _warnings
sys.modules["warnings"] = None
with _io.open("src.txt", "w") as f:
    f.write("one\ntwo\n")
class Name(str):
    def __getitem__(self, i):
        return "<" if i == 0 else ">"
_warnings.warn_explicit("m", UserWarning, Name("src.txt"), 2)
'''),
    ('RL-462', "reversed.__setstate__ and the state's __int__", r'''
class State(int):
    def __int__(self): return 0
it = reversed((1, 2))
it.__setstate__(State(1))
print(next(it))
'''),
    ('RL-463', "a private method's __reduce__ and a metaclass's __name__", r'''
class M(type):
    @property
    def __name__(cls): return "Other"
class C(metaclass=M):
    def __f(self): pass
print(C()._C__f.__reduce__()[1][1])
'''),
    ('RL-464', 'reversed and an exception whose __class__ lies', r'''
class Impostor(Exception):
    @property
    def __class__(self): return IndexError
class Seq:
    def __len__(self): return 1
    def __getitem__(self, index): raise Impostor()
try: next(reversed(Seq()))
except BaseException as e: print(type(e).__name__)
'''),
    ('RL-470', 'a range too long for a length', r'''
r = range(2**63)
big = range(10**400)
ROWS = {
    "list(r)": lambda: list(r),
    "[*r]": lambda: [*r],
    "list(iter(r))": lambda: list(iter(r)),
    "list(reversed(r))": lambda: list(reversed(r)),
    "[].extend(r)": lambda: [].extend(r),
    "[] += r": lambda: [].__iadd__(r),
    "sorted(r)": lambda: sorted(r),
    "list(big)": lambda: list(big),
    "list(iter(big))": lambda: list(iter(big)),
    "bytes(r)": lambda: bytes(r),
    "bytearray(r)": lambda: bytearray(r),
    "list(range(2**63 - 1, 2**63 + 2))": lambda: list(range(2**63 - 1, 2**63 + 2)),
    "list(range(0, 2**70, 2**68))": lambda: list(range(0, 2**70, 2**68)),
    "len(r)": lambda: len(r),
}
for label, work in ROWS.items():
    try:
        out = repr(work())[:60]
    except (OverflowError, MemoryError, ValueError, TypeError) as exc:
        out = type(exc).__name__ + " " + repr(exc.args)
    print(label, "->", out, flush=True)
'''),
    ('RL-472', "close: the flush's failure is the close's context", r'''
import io
class Raw(io.RawIOBase):
    def writable(self): return True
    def write(self, b): raise OSError("write failed")
    def close(self): raise ValueError("close failed")
w = io.BufferedWriter(Raw())
w.write(b"x")
try:
    w.close()
except ValueError as e:
    print(type(e.__context__).__name__, type(e.__cause__).__name__, e.__suppress_context__)
'''),
    ('RL-473', 'zip and map, strict: no StopIteration behind the ValueError', r'''
names = ["a", "b", "c"]; values = [1, 2]
for n, v in zip(names, values, strict=True):
    print(n, v)
'''),
    ('RL-479', "throw: the metaclass's __subclasscheck__", r'''
class Meta(type):
    def __subclasscheck__(cls, sub):
        return True
class M(Exception, metaclass=Meta): pass
def catcher():
    while True:
        try:
            yield
        except BaseException as e:
            yield e
g = catcher(); next(g)
r = g.throw(M, ValueError("v"))
print(type(r).__name__, r.args)

class Meta2(type):
    def __subclasscheck__(cls, sub):
        print("subclasscheck called"); return False
class M2(Exception, metaclass=Meta2): pass
g = catcher(); next(g)
r = g.throw(M2, M2("v"))
print(type(r).__name__, r.args)
'''),
    ('RL-480', "throw: a class that gives another class's instance", r'''
class Base(Exception):
    def __new__(cls, *a):
        print("Base.__new__", cls.__name__, [type(x).__name__ for x in a])
        if cls is Base:
            return Sub(*a)
        return super().__new__(cls, *a)
class Sub(Base): pass
def catcher():
    while True:
        try:
            yield
        except BaseException as e:
            yield e
g = catcher(); next(g)
r = g.throw(Base, "x")
print(type(r).__name__, r.args)
'''),
    ('RL-481', 'close: a close attribute that raises', r'''
class BadClose:
    def __iter__(self): return self
    def __next__(self): return 1
    @property
    def close(self): raise RuntimeError("close attr")
def deleg(x):
    yield from x
g = deleg(BadClose()); next(g)
print("close ->", g.close())
g = deleg(BadClose()); next(g)
try:
    g.throw(GeneratorExit)
except BaseException as e:
    print(type(e).__name__)
'''),
    ('RL-482', 'a wrong number of arguments: no entry for the function', r'''
import traceback
def f():
    pass
try:
    f(1)
except TypeError as e:
    print([(x.name, x.lineno) for x in traceback.extract_tb(e.__traceback__)])
    print(e.__traceback__.tb_next is None)
f(1)
'''),
    ('RL-482', 'the same through a lambda, __init__ and a generator function', r'''
import traceback
def f(a, b): pass
class C:
    def __init__(self, a): pass
for fn in (lambda: f(), lambda: C()):
    try:
        fn()
    except TypeError as e:
        print([x.name for x in traceback.extract_tb(e.__traceback__)])
'''),
    ('RL-487', 'a comprehension in a nested block: co_varnames and locals()', r'''
def r1(a):
    if a:
        s = 1
        r = [(w := i) for i in range(a)]
    return locals()
print(list(r1(2)), r1.__code__.co_varnames)

def r4(a):
    for q in a:
        s = [(w := i) for i in range(q)]
        t = 1
    return list(locals())
print(r4([1, 2]), r4.__code__.co_varnames)
'''),
    ('RL-490', "a global a comprehension's := assigns", r'''
def r5(a):
    global GG
    r = [(GG := i) for i in range(a)]
print(r5.__code__.co_varnames, r5.__code__.co_nlocals)
'''),
    ('RL-496', 'a handler that resizes the bytearray a match reads', r'''
import re
import signal

# a handler that resizes the bytearray a match is reading: every entry point holds the buffer, so the resize fails
for name in ("match", "search", "fullmatch", "findall", "split", "sub", "finditer"):
    subject = bytearray(b"a" * 30 + b"b")

    def on_alarm(signum, frame, subject=subject):
        signal.setitimer(signal.ITIMER_REAL, 0)
        subject.extend(b"c" * 4096)

    signal.signal(signal.SIGALRM, on_alarm)
    signal.setitimer(signal.ITIMER_REAL, 0.05)
    pattern = re.compile(rb"(a+)+$")
    try:
        if name == "sub":
            out = pattern.sub(b"x", subject)
        elif name == "finditer":
            out = list(pattern.finditer(subject))
        else:
            out = getattr(pattern, name)(subject)
        print(name, "returned", out, len(subject))
    except BufferError as exc:
        print(name, "BufferError", exc.args, len(subject))
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
    subject.append(1)
    print("   afterwards the bytearray grows again:", len(subject))
'''),
    ('RL-501', "__file__ after the program's body", r'''
import atexit, sys
def bye():
    try:
        print(__file__[-6:])
    except NameError as e:
        print("NameError", e.args)
    print(hasattr(sys.modules["__main__"], "__file__"))
atexit.register(bye)
'''),
    ('RL-503', 'defaultdict | frozendict', r'''
import collections
dd = collections.defaultdict(list, {1: 2})
r = dd | frozendict({1: 5})
print(type(r).__name__, r)
import types
r = types.MappingProxyType(dd) | frozendict({1: 5})
print(type(r).__name__, r)
'''),
    ('RL-510', 'the report folds a recursion', r'''
def rec(n):
    return rec(n + 1)
rec(0)
'''),
    ('RL-511', 'sys.tracebacklimit in the report', r'''
import sys


def a(): b()
def b(): c()
def c(): raise ValueError("deep")


for limit in (None, 0, 1, 2, 3, 4, 5, 10, -1, True, False, 2**70, -2**70, 1.5, "2"):
    if limit is None:
        if hasattr(sys, "tracebacklimit"):
            del sys.tracebacklimit
    else:
        sys.tracebacklimit = limit
    print(f"== limit {limit!r}", file=sys.stderr)
    try:
        a()
    except ValueError as exc:
        sys.__excepthook__(type(exc), exc, exc.__traceback__)
'''),
    ('RL-512', 'a group whose exceptions is None', r'''
class G(ExceptionGroup):
    @property
    def exceptions(self):
        return None
raise G("g", [ValueError(1)])
'''),
    ('RL-513', 'notes whose iteration raises', r'''
import collections.abc
class Seq(collections.abc.Sequence):
    def __len__(self): return 1
    def __getitem__(self, i): raise RuntimeError("no notes today")
e = ValueError("m")
e.__notes__ = Seq()
raise e
'''),
    ('RL-515', 'a SyntaxError made by hand', r'''
raise SyntaxError("invalid syntax", ("file.py", 3, 5, "x y z\n", 3, 6))
'''),
    ('RL-516', "the report's writes to a replaced sys.stderr", r'''
import sys
class Cap:
    def __init__(self): self.w = []; self.f = 0
    def write(self, s): self.w.append(s); return len(s)
    def flush(self): self.f += 1
c = Cap(); old = sys.stderr; sys.stderr = c
e = ValueError("v"); e.__cause__ = KeyError("k")
sys.__excepthook__(type(e), e, None)
sys.stderr = old
print(c.w, c.f)
'''),
    ('RL-518', 'the unraisable hook and a value whose str() raises', r'''
import sys
got = []; sys.unraisablehook = got.append
class D:
    def __del__(self): raise ValueError("v")
d = D(); del d
class Bad:
    def __str__(self): raise RuntimeError("badstr")
sys.__unraisablehook__(type(got[0])((ValueError, Bad(), None, "m", None)))
'''),
    ('RL-519', "a metaclass's __module__ and __qualname__; a SystemExit with no sys.stderr", r'''
import sys


class M(type):
    @property
    def __module__(cls):
        return "meta.mod"


class E(Exception, metaclass=M):
    pass


class F(Exception):
    pass


F.__qualname__ = "Renamed.Inside"      # a property of a metaclass under this name is refused when the metaclass is made (RL-562)


class G(Exception):
    pass


G.__module__ = 7
for exc in (E("m"), F("f"), G("g"), E(), KeyError("k")):
    sys.__excepthook__(type(exc), exc, None)
print("the five hook calls returned")   # reaches: the five hook calls returned
sys.stderr = None
raise SystemExit("bye on the C stream")
'''),
    ('RL-522', 'a buffered writer after a close that failed', r'''
import io


class Raw(io.RawIOBase):
    closes = 0

    def writable(self):
        return True

    def write(self, b):
        raise OSError("write failed")

    def close(self):
        Raw.closes += 1
        raise ValueError("close failed")


def chain(exc):
    out = []
    seen = exc.__context__
    while seen is not None and len(out) < 4:
        out.append(type(seen).__name__ + ":" + str(seen))
        seen = seen.__context__
    return out


raw = Raw()
w = io.BufferedWriter(raw)
w.write(b"x")
for turn in range(3):
    try:
        w.close()
        print(turn, "closed without error")
    except Exception as e:
        print(turn, type(e).__name__, str(e), chain(e), "closes", Raw.closes)
    try:
        print("   closed:", w.closed)
    except Exception as e:
        print("   closed raises", type(e).__name__, str(e))
    try:
        print("   write:", w.write(b"y"))
    except Exception as e:
        print("   write raises", type(e).__name__, str(e))
    try:
        print("   flush:", w.flush())
    except Exception as e:
        print("   flush raises", type(e).__name__, str(e), chain(e))
print("deleting the writer")
del w
print("deleted; closes", Raw.closes)
'''),
    ('RL-461', 'the warning printer and a line that is a str subclass', r'''
import io
import sys
import _io
import _warnings

sys.modules["warnings"] = None
with _io.open("src.txt", "w") as f:
    f.write("one\ntwo\n")


class Line(str):
    def __getitem__(self, i):
        return "Q"

    def __len__(self):
        return 1

    def __str__(self):
        return "stringified"


class Lines:
    def __init__(self, lines):
        self.lines = list(lines)

    def readline(self):
        return self.lines.pop(0) if self.lines else ""

    def close(self):
        pass


class Wrote:
    def __init__(self):
        self.pieces = []

    def write(self, text):
        self.pieces.append((type(text).__name__, str.__str__(text)))


for given in ([Line("  indented subclass\n"), Line("  second\n")], [Line("no new line")], [b"bytes line\n"], [5]):
    io.TextIOWrapper = lambda b, e, given=given: Lines(given)
    kept, sys.stderr = sys.stderr, Wrote()
    try:
        _warnings.warn_explicit("m", UserWarning, "src.txt", 1)
        _warnings.warn_explicit("m", UserWarning, "src.txt", 2)
        pieces = sys.stderr.pieces
    finally:
        sys.stderr = kept
    print(pieces)
'''),
    ('RL-523', 'time: an int field past a C long', r'''
import time


class Index:
    def __init__(self, value):
        self.value = value

    def __index__(self):
        return self.value


CALLS = (("asctime year", lambda v: time.asctime((v, 1, 1, 0, 0, 0, 0, 1, 0))), ("mktime mon", lambda v: time.mktime((2000, v, 1, 0, 0, 0, 0, 1, 0))),
         ("strftime sec", lambda v: time.strftime("%S", (2000, 1, 1, 0, 0, v, 0, 1, 0))), ("clock_getres", time.clock_getres))
for value in (2**31 - 1, 2**31, 2**40, 2**63 - 1, 2**63, 2**64, 2**100, -2**31, -2**31 - 1, -2**63, -2**63 - 1, -2**100, Index(2**70), Index(2**31)):
    for name, call in CALLS:
        shown = f"Index({value.value})" if isinstance(value, Index) else value
        try:
            print(name, shown, "->", type(call(value)).__name__)
        except (OverflowError, ValueError, OSError) as exc:
            print(name, shown, "->", type(exc).__name__, exc)
'''),
]


def _report(text: str) -> list[str]:
    text = re.sub(r" at 0x[0-9a-f]+", "", text)
    text = re.sub(r'File "[^"]*/([^"/]+)"', r'File "\1"', text)
    text = re.sub(r'(^|\s)/[^\s:"]*/([^/\s:"]+\.py)', r"\1\2", text, flags=re.MULTILINE)
    return mask_stderr(text).splitlines()


def same(source: str) -> None:
    if shutil.which("g++") is None:
        return
    env = dict(os.environ, PYTHONHASHSEED="0")
    with tempfile.TemporaryDirectory() as tmp:
        prog = Path(tmp, "prog.py")
        prog.write_text(source, encoding="utf-8")
        ref = subprocess.run([sys.executable, "prog.py"], capture_output=True, text=True, check=False, env=env, cwd=tmp, stdin=subprocess.DEVNULL)
        got = subprocess.run([str(build(prog, "prog.py"))], capture_output=True, text=True, check=False, env=env, cwd=tmp, stdin=subprocess.DEVNULL)
    # a program says what it has to reach ("# reaches: text"): two runs that end alike before it prove nothing (RL-562)
    for must in re.findall(r"# reaches: (.+)$", source, flags=re.MULTILINE):
        assert must in ref.stdout, f"CPython never reached {must!r}:\n{ref.stdout}{ref.stderr}"
    have = (re.sub(r" at 0x[0-9a-f]+", "", got.stdout), got.returncode, _report(got.stderr))
    want = (re.sub(r" at 0x[0-9a-f]+", "", ref.stdout), ref.returncode, _report(ref.stderr))
    assert have == want, (f"\n--- compiled (exit {got.returncode})\n{got.stdout}{got.stderr}\n"
                          f"--- CPython (exit {ref.returncode})\n{ref.stdout}{ref.stderr}")


def pytest_generate_tests(metafunc: Any) -> None:
    if "finding" in metafunc.fixturenames:
        metafunc.parametrize("finding", FINDINGS, ids=[f"{rl}-{name}" for rl, name, _ in FINDINGS])


def test_finding(finding: tuple[str, str, str]) -> None:
    same(finding[2])


if __name__ == "__main__":
    for item in FINDINGS:
        test_finding(item)
    print("ok")
