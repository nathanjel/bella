"""input() and breakpoint(), compiled, against CPython: the words of the errors case C-6-22 compares by class, the terminal's way
(PyOS_Readline) through a pseudo-terminal, breakpoint() where pdb cannot be imported (D-11), and the names site adds to
builtins, which a compiled program does not have (spec section 6; D-18)."""
from __future__ import annotations

import atexit
import os
import re
import shutil
import subprocess
import sys
import tempfile
import textwrap
import time
from pathlib import Path

from pipeline.build import build
from pipeline.tests.test_review_2026_11_03 import same

WORDS = r"""
import io, sys
real_in, real_out, real_err = sys.stdin, sys.stdout, sys.stderr
def m(f):
    try:
        return repr(f())
    except BaseException as e:
        return type(e).__name__ + ": " + str(e) + " " + repr(e.args)
LOG = []
class Stream:
    def __init__(self, name, lines=(), fd=None, broken=()):
        self.name, self.lines, self.fd, self.broken = name, list(lines), fd, broken
    def flush(self):
        LOG.append(self.name + ".flush")
        if "flush" in self.broken: raise OSError("flush failed")
        if "interrupt" in self.broken: raise KeyboardInterrupt("in flush")
    def fileno(self):
        LOG.append(self.name + ".fileno")
        if "interrupt" in self.broken: raise KeyboardInterrupt("in fileno")
        if self.fd is None: raise io.UnsupportedOperation("fileno")
        return self.fd
    def write(self, text):
        LOG.append(self.name + ".write " + repr(text))
        if "write" in self.broken: raise OSError("write failed")
        return len(text)
    def readline(self, *args):
        LOG.append(self.name + ".readline" + repr(args))
        return self.lines.pop(0) if self.lines else ""
class Index:
    def __index__(self): return 7
class Sub(str):
    pass
class Named:
    encoding = "utf-8"
    errors = "strict"
    def fileno(self): return 0
    def flush(self): pass
    def readline(self): return "named\n"
    def write(self, text): LOG.append("named.write " + repr(text))
def run(prompt, fin, fout=None, ferr=None):
    LOG.clear()
    sys.stdin, sys.stdout, sys.stderr = fin, fout or Stream("out"), ferr or Stream("err")
    try:
        result = m(lambda: input(*prompt))
    finally:
        sys.stdin, sys.stdout, sys.stderr = real_in, real_out, real_err
    return result, list(LOG)
print(run((), Stream("in", [])), run((), Stream("in", [b""])))
print(run((), Stream("in", [5])), run((), Stream("in", [None])), run((), Stream("in", [bytearray(b"x")])), run((), Stream("in", [Sub("sub\n")])))
print(run(("p",), Stream("in", ["x\n"], fd="zero")), run(("p",), Stream("in", ["x\n"], fd=2 ** 70)), run(("p",), Stream("in", ["x\n"], fd=1.5)))
print(run(("p",), Stream("in", ["x\n"], fd=Index())), run(("p",), Stream("in", ["x\n"], fd=True)), run(("p",), Stream("in", ["x\n"], fd=-2 ** 63 - 1)))
print(run(("p",), Named()), run(("p",), Stream("in", ["x\n"], fd=0), Named()))
print(run(("p",), object()), run(("p",), Stream("in", ["x\n"]), object()), run(("p",), Stream("in", ["x\n"]), None, object()))
print(run(("p",), Stream("in", ["x\n"]), Stream("out", broken=("write",))), run((), Stream("in", ["x\n"]), Stream("out", broken=("flush",)), Stream("err", broken=("flush",))))
print(run((), Stream("in", ["x\n"]), Stream("out", broken=("interrupt",)), Stream("err", broken=("interrupt",))), run((), Stream("in", ["x\n"], broken=("interrupt",))))
for missing in ("stdin", "stdout", "stderr"):
    saved = getattr(sys, missing)
    setattr(sys, missing, None)
    try:
        a = m(lambda: input())
    finally:
        setattr(sys, missing, saved)
    delattr(sys, missing)
    try:
        b = m(lambda: input())
    finally:
        setattr(sys, missing, saved)
    print(missing, a, b)
print(m(lambda: input(prompt="x")), m(lambda: input("a", "b")), m(lambda: input(*"abc")), m(lambda: input("a", "b", c=1)), type(input).__name__, input.__name__,
      input.__module__, input.__qualname__, input.__self__.__name__)
print(input.__doc__, breakpoint.__doc__, type(breakpoint).__name__, breakpoint.__name__, breakpoint.__module__, breakpoint.__qualname__)
sys.stdin = io.StringIO("first\nsecond\n\nlast")
print(repr(input()), repr(input("? ")), repr(input()), repr(input()), m(input))
sys.stdin = real_in
"""

# what a terminal session does: the program, what is typed (with pauses), and whether a signal is sent while it waits
TERMINAL = {
    "a line": ("print(repr(input('name? ')), repr(input()))\n", [b"Zo\xc3\xab\n", b"second\n"], None),
    "the end of the input": ("try:\n    input('? ')\nexcept EOFError as exc:\n    print('EOFError', exc.args)\n", [b"\x04"], None),
    # the first end only hands over what was typed, the second ends the read of that piece, the third the next read: the line's last
    # character goes with the newline that is not there
    "the end after part of a line": ("print(repr(input('? ')))\n", [b"abc", b"\x04", b"\x04", b"\x04"], None),
    "a prompt that is no str": ("print(repr(input(5)), repr(input(None)), repr(input(b'b')))\n", [b"1\n", b"2\n", b"3\n"], None),
    "a null in the prompt": ("try:\n    input('a\\0b')\nexcept ValueError as exc:\n    print('ValueError', exc)\n", [], None),
    "a prompt the terminal cannot show": ("import sys\nprint(sys.stdout.errors, sys.stdin.errors)\ntry:\n    print(repr(input('\\udc80> ')))\nexcept UnicodeError as exc:\n"
                                          "    print(type(exc).__name__, exc)\n", [b"x\n"], None),
    "bytes that are no text": ("import sys\ntry:\n    print(ascii(input('? ')))\nexcept UnicodeError as exc:\n    print(type(exc).__name__)\n", [b"\xff\xfe\n"], None),
    "a stream that is no terminal's": ("import io, sys\nsys.stdout.flush()\nkept = sys.stdin\nclass Zero:\n    def fileno(self): return 0\n    def readline(self): return 'from readline\\n'\n"
                                       "sys.stdin = Zero()\nprint(repr(input('? ')))\nsys.stdin = kept\n", [], None),
    "a handler that returns": ("import os, signal\nsignal.signal(signal.SIGUSR1, lambda signum, frame: print('handled', flush=True))\nprint(os.getpid(), flush=True)\n"
                               "print(repr(input('? ')))\n", [b"after\n"], "SIGUSR1"),
    "a handler that raises": ("import os, signal\nclass Stop(Exception):\n    pass\ndef handler(signum, frame):\n    raise Stop(signum)\nsignal.signal(signal.SIGUSR1, handler)\n"
                              "print(os.getpid(), flush=True)\ntry:\n    input('? ')\nexcept Stop as exc:\n    print('Stop', exc.args)\n", [], "SIGUSR1"),
    "an interrupt": ("import os\nprint(os.getpid(), flush=True)\ntry:\n    input('? ')\nexcept KeyboardInterrupt as exc:\n    print('KeyboardInterrupt', exc.args)\n", [], "SIGINT"),
}

BREAKPOINT = r"""
import os, sys, warnings
print(sys.modules.setdefault("pdb", None))       # CPython's pdb, unimportable: what a compiled program is (D-11)
with warnings.catch_warnings(record=True) as caught:
    warnings.simplefilter("always")
    print(breakpoint(), breakpoint(1, key=2))
print([(type(w.message).__name__, str(w.message), w.category.__name__, w.lineno) for w in caught])
os.environ["PYTHONBREAKPOINT"] = "0"
with warnings.catch_warnings(record=True) as caught:
    warnings.simplefilter("always")
    print(breakpoint(), breakpoint(1, key=2), caught)
os.environ["PYTHONBREAKPOINT"] = ""
warnings.simplefilter("error")
try:
    breakpoint()
except RuntimeWarning as exc:
    print("RuntimeWarning", exc)
warnings.simplefilter("always")
sys.breakpointhook = lambda *args, **kws: ("the program's hook", args, kws)
print(breakpoint(), breakpoint(1, 2, key=3))
sys.breakpointhook = None
try:
    breakpoint()
except TypeError as exc:
    print("TypeError", exc)
"""

SITE = r"""
import builtins
def m(f):
    try:
        return repr(f())
    except BaseException as e:
        return type(e).__name__ + ": " + str(e)
print(m(lambda: exit), m(lambda: quit), m(lambda: help), m(lambda: copyright), m(lambda: credits), m(lambda: license))
print(m(lambda: builtins.exit), hasattr(builtins, "quit"), [n for n in ("exit", "quit", "help", "copyright", "credits", "license") if n in dir(builtins) or n in vars(builtins)])
def leaves():
    exit(3)
print(m(leaves))
"""


def _both(source: str) -> tuple[Path, Path]:
    tmp = Path(tempfile.mkdtemp())
    atexit.register(shutil.rmtree, tmp, ignore_errors=True)       # the caller runs the program there, so it goes with the process
    prog = tmp / "prog.py"
    prog.write_text(textwrap.dedent(source), encoding="utf-8")
    return prog, build(prog, "prog.py")


def _session(command: list[str], cwd: Path, typed: list[bytes], signal_name: str | None) -> tuple[str, str, int]:
    """Run `command` with its stdin and stdout on a pseudo-terminal and its stderr on a pipe. Once its prompt is there (stderr has
    something), send the signal if one is named, then type the pieces, a pause before each; what the terminal showed, what stderr
    got, and how the program ended."""
    import pty
    import select
    import signal
    master, slave = pty.openpty()
    env = dict(os.environ, PYTHONHASHSEED="0", TERM="dumb")
    env.pop("PYTHONBREAKPOINT", None)
    proc = subprocess.Popen(command, stdin=slave, stdout=slave, stderr=subprocess.PIPE, cwd=cwd, env=env, start_new_session=True)
    os.close(slave)
    assert proc.stderr is not None
    errors = proc.stderr.fileno()
    os.set_blocking(errors, False)
    shown = b""
    err = b""

    def read_some(wait: float, until_prompt: bool = False) -> None:
        nonlocal shown, err
        end = time.monotonic() + wait
        while time.monotonic() < end and not (until_prompt and err):
            ready, _, _ = select.select([master, errors], [], [], 0.05)
            for fd in ready:
                try:
                    data = os.read(fd, 4096)
                except OSError:                  # the terminal's other end is closed
                    data = b""
                if fd == master:
                    shown += data
                else:
                    err += data
            if proc.poll() is not None and not ready:
                return
    if typed or signal_name is not None:
        read_some(60.0, until_prompt=True)       # the program is in its read, its handlers installed
        read_some(0.2)
    if signal_name is not None:
        os.kill(proc.pid, getattr(signal, signal_name))
        read_some(0.5)
    for piece in typed:
        os.write(master, piece)
        read_some(0.4)
    limit = time.monotonic() + 60.0
    while proc.poll() is None and time.monotonic() < limit:
        read_some(0.2)
    if proc.poll() is None:
        proc.kill()
    proc.wait()
    read_some(0.3)
    os.close(master)
    proc.stderr.close()
    text = shown.decode("utf-8", "backslashreplace").replace("\r\n", "\n")
    return re.sub(r"^\d{4,}$", "<pid>", text, flags=re.MULTILINE), err.decode("utf-8", "backslashreplace"), proc.returncode


def test_the_words() -> None:
    same(WORDS)


PIPED = r"""
import sys
print(repr(input("first? ")), repr(input()), repr(sys.stdin.readline()), repr(input("after a read? ")))
for _ in range(3):
    try:
        print(repr(input("more? ")))
    except EOFError as exc:
        print("EOFError", exc.args)
"""


def test_from_a_pipe_and_a_file() -> None:
    """The process's own stdin when it is no terminal: sys.stdin's readline(), with the prompt on stdout."""
    if shutil.which("g++") is None:
        return
    prog, binary = _both(PIPED)
    try:
        for given in (b"one\ntwo\nthree\nfour\nlast, no newline", b"\xc5\xbc\r\n\n", b""):
            ref = subprocess.run([sys.executable, str(prog)], input=given, capture_output=True, check=False, cwd=prog.parent)
            got = subprocess.run([str(binary)], input=given, capture_output=True, check=False, cwd=prog.parent)
            assert (got.stdout, got.returncode) == (ref.stdout, ref.returncode), f"{given!r}\n--- compiled\n{got}\n--- CPython\n{ref}"
            with open(prog.parent / "in.txt", "wb") as f:
                f.write(given)
            with open(prog.parent / "in.txt", "rb") as a, open(prog.parent / "in.txt", "rb") as b:
                ref = subprocess.run([sys.executable, str(prog)], stdin=a, capture_output=True, check=False, cwd=prog.parent)
                got = subprocess.run([str(binary)], stdin=b, capture_output=True, check=False, cwd=prog.parent)
            assert (got.stdout, got.returncode) == (ref.stdout, ref.returncode), f"{given!r} from a file\n--- compiled\n{got}\n--- CPython\n{ref}"
    finally:
        shutil.rmtree(prog.parent)


def test_at_a_terminal() -> None:
    """Both programs at a pseudo-terminal: the prompt goes to the C stderr, the line comes from the C stdin, and the terminal's
    own echo is the same for both."""
    if shutil.which("g++") is None:
        return
    try:
        import pty
        master, slave = pty.openpty()
    except (ImportError, OSError):
        return                                   # no pseudo-terminals here
    os.close(master)
    os.close(slave)
    for name, (source, typed, signal_name) in TERMINAL.items():
        prog, binary = _both(source)
        try:
            ref = _session([sys.executable, str(prog)], prog.parent, typed, signal_name)
            got = _session([str(binary)], prog.parent, typed, signal_name)
        finally:
            shutil.rmtree(prog.parent)
        assert got == ref, f"{name}\n--- compiled\n{got}\n--- CPython\n{ref}"


def test_breakpoint_where_pdb_cannot_be_imported() -> None:
    same(BREAKPOINT)
    if shutil.which("g++") is None:
        return
    env = {k: v for k, v in os.environ.items() if k != "PYTHONBREAKPOINT"}
    # the program imports warnings: a warning is shown through it, and the build links what the program imports (a program without
    # it stops where the runtime asks for the module, as at any other warning of the runtime's: TODO, the runtime's own imports)
    prog, binary = _both("import warnings\nprint('before')\nprint(breakpoint())\nprint('after')\n")
    try:
        got = subprocess.run([str(binary)], capture_output=True, text=True, check=False, cwd=prog.parent, env=env)
        assert (got.returncode, got.stdout) == (0, "before\nNone\nafter\n"), got
        assert got.stderr.startswith('prog.py:3: RuntimeWarning: Ignoring unimportable $PYTHONBREAKPOINT: "pdb.set_trace"\n'), got
        named = subprocess.run([str(binary)], capture_output=True, text=True, check=False, cwd=prog.parent, env=dict(env, PYTHONBREAKPOINT="os.getcwd"))
        assert (named.returncode, named.stdout) == (70, "before\n") and "PYTHONBREAKPOINT naming a hook (os.getcwd" in named.stderr, named
    finally:
        shutil.rmtree(prog.parent)


def test_the_names_site_adds_are_not_there() -> None:
    """CPython without site (-S) is the reference: a compiled program runs none (D-18)."""
    if shutil.which("g++") is None:
        return
    prog, binary = _both(SITE)
    try:
        ref = subprocess.run([sys.executable, "-S", str(prog)], capture_output=True, text=True, check=False, cwd=prog.parent)
        got = subprocess.run([str(binary)], capture_output=True, text=True, check=False, cwd=prog.parent)
    finally:
        shutil.rmtree(prog.parent)
    assert (got.stdout, got.returncode) == (ref.stdout, ref.returncode), f"\n--- compiled\n{got.stdout}{got.stderr}\n--- CPython -S\n{ref.stdout}{ref.stderr}"


if __name__ == "__main__":
    test_the_words()
    test_from_a_pipe_and_a_file()
    test_at_a_terminal()
    test_breakpoint_where_pdb_cannot_be_imported()
    test_the_names_site_adds_are_not_there()
