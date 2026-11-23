"""An argument that is an instance of a subclass of a built-in type, where CPython's C reads the object's own data (RL-698).

Once a C function has tested that its argument is a str, a bytes, an int, a tuple, a list or a dict, it reads the data
through the concrete API (PyUnicode_*, PyBytes_AS_STRING, PyLong_As*, PyTuple_GET_ITEM, PyList_GET_ITEM, PyDict_Next),
which calls nothing of the object's class. A prelude that stands for such a function and writes `len(x)`, `x[i]`,
`x == y`, `i in x`, `for c in x`, `bytes(x)` or `int(x)` on the argument reaches whatever a subclass of the program's
overrides. Review A31 found it in 16 preludes, 32 findings of its 41 (RL-657 to RL-697); four gave wrong data: a digest
of other bytes, `compare_digest` true for unequal bytes, a JSON text with another key and value, a struct field with
another byte. The preludes take the data once now (`_own_data`, `_buffer_bytes`, the base type's own methods).

The sweep is the reviewer's driver (`subclass_data_sweep.txt`, a program kept beside this file): 462 calls of the library
with instances of S, I, F, B, A, T, L and D, subclasses of str, int, float, bytes, bytearray, tuple, list and dict in which
every overridable method logs its name and then answers as the base does (`log`) or raises (`raise`). A process for each
row and mode, compiled against CPython: the result and the methods that were called, which must be the same list.
Before the change 244 of its 924 runs differed. The second program is the report's reduced reproductions.

Run under pytest or directly: python3 -m pipeline.tests.test_subclass_data
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from pipeline.build import build
from pipeline.tests.test_review_2026_11_19 import same

HERE = Path(__file__).resolve().parent

# rows whose function stops by name (in one mode or in both); the row then holds only that it is one that stops
STOPS = {
    54: "an attribute name of a subclass of str", 55: "an attribute name of a subclass of str", 144: "an attribute name of a subclass of str",
    277: "an attribute name of a subclass of str", 423: "an attribute name of a subclass of str",
    136: "E-01: eval at collections:namedtuple", 181: "_codecs.utf_7_encode",
    187: "_codecs.unicode_escape_encode", 188: "_codecs.raw_unicode_escape_encode", 192: "_codecs.utf_7_decode",
    196: "_codecs.unicode_escape_decode", 197: "_codecs.raw_unicode_escape_decode", 215: "binascii.b2a_qp", 216: "binascii.a2b_qp",
    217: "binascii.b2a_uu", 218: "binascii.a2b_uu", 358: "[P2+] annotationlib", 455: "gc.is_tracked",
}
# a registered deviation that shows in the sweep: without OpenSSL's _hashlib (D-20) hashlib.new looks its constructor up by
# the name in a dict of hashlib.py's own, which hashes a str subclass; CPython's _hashlib.new reads the name's characters
DEVIATES = {305: "D-20"}
# the report's reduced programs: selection 11 is RL-668 (importlib's frames in a traceback), which is open
EXAMPLES_OPEN = {11}


def _both(program: Path, binary: str, arguments: list[str], folder: Path) -> tuple[subprocess.CompletedProcess[str], subprocess.CompletedProcess[str]]:
    env = {**os.environ, "PYTHONHASHSEED": "0"}
    reference, compiled = (subprocess.run([*command, *arguments], capture_output=True, text=True, env=env, cwd=folder, timeout=120,
                                          stdin=subprocess.DEVNULL) for command in ([sys.executable, str(program)], [binary]))
    return reference, compiled


def test_the_data_of_a_subclass_instance_is_read_as_the_c_reads_it() -> None:
    if shutil.which("g++") is None:
        return
    folder = Path(tempfile.mkdtemp(prefix="bella-subclass-"))
    try:
        program = folder / "prog.py"
        program.write_text((HERE / "subclass_data_sweep.txt").read_text(encoding="utf-8"), encoding="utf-8")
        binary = str(build(program, "prog.py", notes=False))
        runs = [(row, mode) for row in range(462) for mode in ("log", "raise")]
        with ThreadPoolExecutor(max_workers=4) as pool:     # a process for each row and mode: one that stops takes no other with it
            results = list(pool.map(lambda run: _both(program, binary, [str(run[0]), run[1]], folder), runs))
        wrong: list[str] = []
        stopped: set[int] = set()
        deviating: set[int] = set()
        for (row, mode), (reference, compiled) in zip(runs, results, strict=True):
            assert reference.returncode == 0, (row, mode, reference.stderr[-300:])
            if compiled.returncode == 70 and "bella: not implemented: " + STOPS.get(row, "\0") in compiled.stderr:
                stopped.add(row)
            elif (compiled.returncode, compiled.stdout) != (reference.returncode, reference.stdout):
                if row in DEVIATES:
                    deviating.add(row)
                else:
                    wrong.append(f"{row} {mode}: compiled {compiled.stdout.strip()[:200]!r} (status {compiled.returncode}, "
                                 f"{compiled.stderr.strip()[-200:]!r}), CPython {reference.stdout.strip()[:200]!r}")
        assert not wrong, "\n".join(wrong)
        assert stopped == set(STOPS), sorted(stopped ^ set(STOPS))
        assert deviating == set(DEVIATES), sorted(deviating ^ set(DEVIATES))
    finally:
        shutil.rmtree(folder, ignore_errors=True)


def test_the_reduced_programs_of_review_a31() -> None:
    if shutil.which("g++") is None:
        return
    folder = Path(tempfile.mkdtemp(prefix="bella-a31-"))
    try:
        program = folder / "prog.py"
        program.write_text((HERE / "subclass_data_examples.txt").read_text(encoding="utf-8"), encoding="utf-8")
        binary = str(build(program, "prog.py", notes=False))
        wrong: list[str] = []
        for row in range(37):
            if row in EXAMPLES_OPEN:
                continue
            reference, compiled = _both(program, binary, [str(row)], folder)
            assert reference.returncode == 0, (row, reference.stderr[-300:])
            if (compiled.returncode, compiled.stdout) != (reference.returncode, reference.stdout):
                wrong.append(f"{row}: compiled {compiled.stdout.strip()[:200]!r} (status {compiled.returncode}, {compiled.stderr.strip()[-200:]!r}), "
                             f"CPython {reference.stdout.strip()[:200]!r}")
        assert not wrong, "\n".join(wrong)
    finally:
        shutil.rmtree(folder, ignore_errors=True)


# the findings of the review that are no part of the class, and what was found beside it
FINDINGS: list[tuple[str, str, str]] = [
    ('RL-678', 'a GeneratorExit thrown by close takes the exception being handled as its context', r'''
import sys
def gen(label):
    try: yield 1
    except GeneratorExit as e: print(label, "| in the generator:", type(e).__name__, type(e.__context__).__name__)
def inside(label):
    try: raise LookupError("its own")
    except LookupError:
        try: yield 1
        except GeneratorExit as e: print(label, "| in a handler of its own:", type(e).__name__, type(e.__context__).__name__)
def outer(label):
    yield from gen(label)
for make in (gen, inside, outer):
    g = make("closed plainly")
    next(g)
    g.close()
    g = make("closed in a handler")
    next(g)
    try: raise KeyError("the caller's")
    except KeyError: g.close()
    g = make("let go in a handler")
    next(g)
    try: raise KeyError("the caller's")
    except KeyError: del g
    g = make("thrown into, in a handler")
    next(g)
    try: raise KeyError("the caller's")
    except KeyError:
        try: g.throw(GeneratorExit())
        except (GeneratorExit, StopIteration) as e: print("   and out came", type(e).__name__)
def raises_in_close():
    try: yield 1
    except GeneratorExit: raise ValueError("while closing")
g = raises_in_close()
next(g)
try:
    try: raise KeyError("the caller's")
    except KeyError: g.close()
except ValueError as e:
    chain = []
    while e is not None:
        chain.append(type(e).__name__)
        e = e.__context__
    print("an error of the close:", chain)
'''),
    ('RL-696', 'repr and str of a bytes or bytearray subclass with a __repr__ of its own', r'''
class B(bytes):
    def __repr__(self): return "B's repr"
class A(bytearray):
    def __repr__(self): return "A's repr"
class BS(bytes):
    def __str__(self): return "BS's str"
class BB(bytes):
    def __repr__(self): return "<" + bytes.__repr__(self) + ">"
class AA(bytearray):
    def __repr__(self): return "<" + bytearray.__repr__(self) + ">"
class Plain(bytes): pass
class PlainA(bytearray): pass
for value in (B(b"ab"), A(b"ab"), BS(b"ab"), BB(b"ab"), AA(b"ab"), Plain(b"ab"), PlainA(b"ab"), b"ab", bytearray(b"ab")):
    print(type(value).__name__, "|", repr(value), "|", str(value), "|", "%s %r %a" % (value, value, value), "|", format(value), "|",
          f"{value} {value!r} {value!s}", "|", [value], "|", (value,), "|", {1: value}, "|",
          bytes.__repr__(value) if isinstance(value, bytes) else bytearray.__repr__(value), "|", object.__str__(value))
print(B(b"ab"), A(b"ab"), BS(b"ab"))
'''),
    ('RL-697', 'an argv whose length cannot be taken is an empty argv', r'''
import os
class L(list):
    def __len__(self): raise LookupError("len")
class Stops(list):
    def __len__(self): raise KeyboardInterrupt
class Empty(list):
    def __len__(self): return 0
for name, call in (("execv", lambda argv: os.execv("/a31-not-present", argv)), ("execve", lambda argv: os.execve("/a31-not-present", argv, {})),
                   ("posix_spawn", lambda argv: os.posix_spawn("/a31-not-present", argv, {})), ("posix_spawnp", lambda argv: os.posix_spawnp("a31-not-present", argv, {}))):
    for kind in (L, Stops, Empty):
        try: call(kind(["x"]))
        except BaseException as e: print(name, kind.__name__, "->", type(e).__name__, type(e.__context__).__name__)
    try: call(["x"])
    except BaseException as e: print(name, "a list ->", type(e).__name__)
'''),
    ('RL-664', 'struct keeps a str format object as the key of its cache, and a bytes format by its text', r'''
import struct
events = []
class Format(str):
    def __hash__(self):
        events.append("hash")
        return str.__hash__(self)
    def __eq__(self, other):
        events.append("eq")
        return str.__eq__(self, other)
    def __del__(self): events.append("gone")
class Bytes(bytes):
    def __hash__(self):
        events.append("hash of bytes")
        return bytes.__hash__(self)
    def __del__(self): events.append("gone")
class Unhashable(str):
    __hash__ = None
class Raises(str):
    def __hash__(self): raise LookupError("hash")
def attempt(label, act):
    try: print(label, "->", act(), events)
    except Exception as e: print(label, "->", type(e).__name__, events)
    events.clear()
struct._clearcache()
f = Format("<2s")
attempt("calcsize, first", lambda: struct.calcsize(f))
attempt("calcsize, again", lambda: struct.calcsize(f))
attempt("pack", lambda: struct.pack(f, b"ab"))
attempt("an equal str", lambda: struct.calcsize("<2s"))
del f
attempt("the format let go, held by the cache", lambda: None)
struct._clearcache()
attempt("the cache cleared", lambda: None)
b = Bytes(b"<2s")
attempt("a bytes format", lambda: struct.calcsize(b))
del b
attempt("the bytes format let go", lambda: None)
attempt("an unhashable format", lambda: struct.calcsize(Unhashable("i")))
attempt("a format whose hash raises", lambda: struct.calcsize(Raises("i")))
attempt("a bytearray format", lambda: struct.calcsize(bytearray(b"i")))
attempt("an int format", lambda: struct.calcsize(1))
attempt("Struct of a format object", lambda: (struct.Struct(Format("i")).format, type(struct.Struct(Format("i")).format).__name__))
struct._clearcache()
'''),
    ('RL-669', 'what the library keeps or gives back of a subclass instance: a text stream\'s options, a seek position, a path\'s parts', r'''
import io, os
class S(str): pass
class B(bytes): pass
class Position(int):
    def __int__(self): return 1
with open("/dev/null", S("r"), encoding=S("utf8"), errors=S("strict"), newline=S("")) as stream:
    print("open:", [type(v).__name__ for v in (stream.mode, stream.encoding, stream.errors)])
t = io.TextIOWrapper(io.BytesIO(b"ab"), encoding=S("ascii"), errors=S("strict"), newline=S("\n"))
print("TextIOWrapper:", type(t.encoding).__name__, type(t.errors).__name__, t.errors)
t.seek(Position(0))
print("a position whose __int__ says 1:", repr(t.read()))
s = io.StringIO(S("ab"), S("\n"))
print("StringIO:", type(s.getvalue()).__name__, [type(v).__name__ for v in s.__getstate__()[:2]])
for path in (S("x"), S("/x/y"), S("a//b/../c"), B(b"x"), B(b"/x//y")):
    print(type(path).__name__, [type(part).__name__ for part in os.path.splitroot(path)], type(os.path.normpath(path)).__name__, os.path.normpath(path))
e = UnicodeEncodeError(S("ascii"), S("z"), Position(0), Position(1), S("reason"))
print("UnicodeEncodeError:", [type(v).__name__ for v in (e.encoding, e.object, e.start, e.end, e.reason)], e.start, e.end)
e.start = Position(5)
print("   and a start assigned:", type(e.start).__name__, e.start)
'''),
]


def pytest_generate_tests(metafunc: object) -> None:
    if "finding" in metafunc.fixturenames:  # type: ignore[attr-defined]
        metafunc.parametrize("finding", FINDINGS, ids=[f"{rl}-{name}" for rl, name, _ in FINDINGS])  # type: ignore[attr-defined]


def test_finding(finding: tuple[str, str, str]) -> None:
    same(finding[2])


if __name__ == "__main__":
    test_the_data_of_a_subclass_instance_is_read_as_the_c_reads_it()
    test_the_reduced_programs_of_review_a31()
    for row in FINDINGS:
        same(row[2])
        print("ok", row[0])
    print("ok")
