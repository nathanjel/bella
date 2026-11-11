"""Signals, compiled, against CPython on the same machine.

What a compiled program starts with: the signals CPython ignores when it starts (SIGPIPE and SIGXFSZ, Modules/signalmodule.c's
signal_install_handlers), seen from outside the program, where case C-7-73 sees them from inside: a reader that has gone is a
BrokenPipeError and exit status 120, a write past the file size limit an OSError.

Signals that reach a compiled program from outside, and the ways a program ends by one: a conformance case cannot hold a row
whose process dies of a signal or that needs a signal sent to it, so those rows are here. A program says "ready" and the test
sends only then; where the program must be found waiting in the system (a sleep, a read) the test first waits until /proc says
it sleeps. Every program, CPython's and compiled, is started with every signal at its default and an empty mask, and every
wait for one is bounded by WAIT seconds, after which the program is killed and the test fails with what the program had said;
a driver that fails for any reason kills what it started. Nothing here sleeps and hopes.

Also here: the words of every refusal of the _signal functions (cases C-7-75 and C-7-76 print classes only), the rows those
cases leave out (a signal left waiting behind a handler that raised, or owed when a call that waits begins; a child that
signals the program), and, at the end and marked so, what a build with fidelity="lean" does instead (deviation D-24), pinned
the way test_instance_dict.py pins D-23."""
from __future__ import annotations

import os
import resource
import select
import shutil
import signal
import subprocess
import sys
import tempfile
import textwrap
import time
from collections.abc import Callable, Sequence
from pathlib import Path

from conformance.harness import mask_stderr
from pipeline.build import build

STDOUT_GONE = r"""
import sys
print("a line nobody reads")
try:
    sys.stdout.flush()
except BrokenPipeError as e:
    print("caught:", e.errno, e.strerror, file=sys.stderr)
print("another")
"""

TOO_LARGE = r"""
import os
import sys
f = open(sys.argv[1], "wb", buffering=0)
try:
    for _ in range(64):
        f.write(b"x" * 65536)
    print("written")
except OSError as e:
    print(type(e).__name__, e.errno, e.strerror, e.filename)
f.close()
print(os.path.getsize(sys.argv[1]) <= 1024 * 1024)
os.unlink(sys.argv[1])
"""


def _limit_file_size() -> None:
    resource.setrlimit(resource.RLIMIT_FSIZE, (262144, resource.getrlimit(resource.RLIMIT_FSIZE)[1]))


def test_a_reader_that_has_gone() -> None:
    if shutil.which("g++") is None:
        return
    outcomes = []
    with tempfile.TemporaryDirectory() as tmp:
        prog = Path(tmp, "prog.py")
        prog.write_text(STDOUT_GONE, encoding="utf-8")
        for command in ([sys.executable, str(prog)], [str(build(prog, "prog.py"))]):
            r, w = os.pipe()
            os.close(r)
            try:
                done = subprocess.run(command, stdin=subprocess.DEVNULL, stdout=w, stderr=subprocess.PIPE, text=True, check=False)
            finally:
                os.close(w)
            outcomes.append((done.stderr, done.returncode))
    assert outcomes[0] == outcomes[1], outcomes
    assert outcomes[0] == ("caught: 32 Broken pipe\nException ignored while flushing sys.stdout:\nBrokenPipeError: [Errno 32] Broken pipe\n", 120), outcomes[0]


def test_a_write_past_the_file_size_limit() -> None:
    if shutil.which("g++") is None:
        return
    outcomes = []
    with tempfile.TemporaryDirectory() as tmp:
        prog = Path(tmp, "prog.py")
        prog.write_text(TOO_LARGE, encoding="utf-8")
        for command in ([sys.executable, str(prog)], [str(build(prog, "prog.py"))]):
            done = subprocess.run([*command, str(Path(tmp, "big.bin"))], stdin=subprocess.DEVNULL, capture_output=True, text=True, check=False, preexec_fn=_limit_file_size)  # noqa: PLW1509
            outcomes.append((done.stdout, done.stderr, done.returncode))
    assert outcomes[0] == outcomes[1], outcomes
    assert outcomes[0] == ("OSError 27 File too large None\nTrue\n", "", 0), outcomes[0]


WAIT = 60.0          # seconds: the bound of every wait for a program (a loaded CI machine; a healthy run takes milliseconds)


# ---------------------------------------------------------------------------------------------------------------------------
# the driver: a program with its three streams on pipes, every wait bounded
# ---------------------------------------------------------------------------------------------------------------------------

def _dispositions(ignored: Sequence[int] = ()) -> Callable[[], None]:
    """What the program inherits, made the same whoever started the tests (`nohup make check &` ignores SIGHUP, a shell's
    background job SIGINT and SIGQUIT, and CPython takes SIGINT only when it finds it at its default): every signal at its
    default but `ignored`, and an empty mask. (subprocess itself puts SIGPIPE and SIGXFSZ back, restore_signals.)"""
    def in_the_child() -> None:
        for number in range(1, signal.NSIG):
            if number not in (signal.SIGKILL, signal.SIGSTOP, 32, 33):
                signal.signal(number, signal.SIG_IGN if number in ignored else signal.SIG_DFL)
        signal.pthread_sigmask(signal.SIG_SETMASK, [])
    return in_the_child


class _Running:
    """A started program, used as `with _Running(...) as running:` so that a driver's failed assertion does not leave it
    running. `line` waits for its next line, `asleep` until it waits in the system, `end` for its end. `merged`: stderr goes
    into the pipe of stdout, which then shows the order in which the two were written."""

    def __init__(self, command: Sequence[str], cwd: str, ignored: Sequence[int] = (), stdin: bool = False, merged: bool = False) -> None:
        self.command = list(command)
        # preexec_fn: the child's dispositions are set between fork and exec
        self.proc = subprocess.Popen(  # noqa: PLW1509
            self.command, stdin=subprocess.PIPE if stdin else subprocess.DEVNULL, stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT if merged else subprocess.PIPE, bufsize=0, cwd=cwd, env=dict(os.environ, PYTHONHASHSEED="0"),
            preexec_fn=_dispositions(ignored))
        self.said = {"stdout": b"", "stderr": b""}       # what has been read of each stream
        self.taken = {"stdout": 0, "stderr": 0}          # how much of it `line` has handed out

    def __enter__(self) -> _Running:
        return self

    def __exit__(self, *exc: object) -> None:
        """Whatever happened in the block, the program is not left running (a spinning one would hold a CPU of the host)."""
        if self.proc.poll() is None:
            self.proc.kill()
            self.proc.wait()
        for pipe in (self.proc.stdin, self.proc.stdout, self.proc.stderr):
            if pipe is not None:
                pipe.close()

    def _fail(self, why: str) -> AssertionError:
        self.proc.kill()
        out, err = self.proc.communicate()
        return AssertionError(f"{why}\n--- {self.command}\n--- stdout\n{(self.said['stdout'] + out).decode(errors='replace')}"
                              f"--- stderr\n{(self.said['stderr'] + (err or b'')).decode(errors='replace')}")

    def line(self, stream: str = "stdout") -> str:
        """The next whole line of a stream, waited for at most WAIT seconds."""
        pipe = self.proc.stdout if stream == "stdout" else self.proc.stderr
        assert pipe is not None
        deadline = time.monotonic() + WAIT
        while b"\n" not in self.said[stream][self.taken[stream]:]:
            left = deadline - time.monotonic()
            if left <= 0 or not select.select([pipe], [], [], left)[0]:
                raise self._fail(f"no line on {stream} within {WAIT} seconds")
            data = os.read(pipe.fileno(), 65536)
            if not data:
                raise self._fail(f"{stream} ended where a line was awaited")
            self.said[stream] += data
        end = self.said[stream].index(b"\n", self.taken[stream]) + 1
        text = self.said[stream][self.taken[stream]:end].decode()
        self.taken[stream] = end
        return text

    def asleep(self) -> None:
        """Wait until the program waits in the system (state S of proc(5): an interruptible sleep), so that the signal sent
        next finds it inside the call and not on its way there."""
        deadline = time.monotonic() + WAIT
        while True:
            try:
                state = Path(f"/proc/{self.proc.pid}/stat").read_text(encoding="utf-8", errors="replace").rpartition(")")[2].split()[0]
            except OSError:
                state = "gone"
            if state == "S":
                return
            if state in ("gone", "Z", "X") or time.monotonic() > deadline:
                raise self._fail(f"the program did not come to wait in the system (state {state})")
            time.sleep(0.002)

    def send(self, number: int) -> None:
        self.proc.send_signal(number)

    def write(self, data: bytes) -> None:
        assert self.proc.stdin is not None
        self.proc.stdin.write(data)

    def end(self) -> tuple[str, str, int]:
        """The program's whole stdout and stderr and how it ended, waited for at most WAIT seconds."""
        try:
            out, err = self.proc.communicate(timeout=WAIT)
        except subprocess.TimeoutExpired:
            raise self._fail(f"the program did not end within {WAIT} seconds") from None
        return (self.said["stdout"] + out).decode(), (self.said["stderr"] + (err or b"")).decode(), self.proc.returncode


def _two(text: str, tmp: str, fidelity: str = "exact") -> list[list[str]]:
    """The program under CPython and compiled: the two commands. (The interactive drivers below need a running program,
    so this is not the switch's helper that builds a program both ways and runs it to its end.)"""
    prog = Path(tmp, "prog.py")
    prog.write_text(textwrap.dedent(text), encoding="utf-8")
    return [[sys.executable, str(prog)], [str(build(prog, "prog.py", fidelity=fidelity))]]


def _run(command: list[str], tmp: str, ignored: Sequence[int] = (), session: bool = False) -> tuple[str, str, int]:
    """A program run to its end: stdout, stderr as the harness masks it, the status. `session`: in a session of its own,
    for a program that signals its process group (the tests' own group must never get that signal)."""
    done = subprocess.run(command, stdin=subprocess.DEVNULL, capture_output=True, text=True, check=False, cwd=tmp, timeout=WAIT,  # noqa: PLW1509
                          env=dict(os.environ, PYTHONHASHSEED="0"), preexec_fn=_dispositions(ignored), start_new_session=session)
    return done.stdout, mask_stderr(done.stderr), done.returncode


def _same(text: str) -> None:
    """What test_review_2026_11_03.same does, but started as every program here is (signals at their defaults, an empty
    mask: a run under `make check &` ignores SIGINT, and CPython then installs no default_int_handler) and bounded by WAIT
    (a mis-ported refusal can turn into a wait for a signal nobody sends): CPython ends well and says nothing on stderr, and
    the compiled program says and does exactly the same."""
    if shutil.which("g++") is None:
        return
    with tempfile.TemporaryDirectory() as tmp:
        cpython, compiled = _two(text, tmp)
        ref = _run(cpython, tmp)
        got = _run(compiled, tmp)
    assert ref[1:] == ("", 0), ref
    assert got == ref, got


def _ends(stderr: str) -> tuple[str, str]:
    """A traceback's first and last line: the lines between say where the signal found the program, which is not the test's."""
    lines = stderr.splitlines()
    return (lines[0], lines[-1]) if lines else ("", "")


# ---------------------------------------------------------------------------------------------------------------------------
# a signal from outside, to a program that computes and to one that waits
# ---------------------------------------------------------------------------------------------------------------------------

# argv: the way of waiting (loop, recursion, naps, sleep, read, itself) and the handler (python: SIGUSR1 and SIGUSR2 get
# handlers of the program; default: nothing is touched; installed: the program gives SIGINT default_int_handler itself).
# The handler writes with os.write: a handler that prints could find itself inside the very flush of "ready" (CPython's
# buffered writer looks for signals after its raw write, Modules/_io/bufferedio.c:2057, and refuses the handler's own write
# with "RuntimeError: reentrant call inside ...", bufferedio.c:301).
WAITING = r"""
import os
import signal
import sys
import time

seen = []


class Stop(Exception):
    pass


def named(handler):
    return handler.name if isinstance(handler, signal.Handlers) else handler.__name__


def note(signum, frame):
    seen.append(signum)
    os.write(1, ("handler " + str(signum) + " " + type(frame).__name__ + "\n").encode())


def stop(signum, frame):
    raise Stop(signum)


def spin():
    while not seen:
        pass
    return "the loop ended"


def walk(depth):
    # 2**64 calls and no loop: only the look at a function's entry can end it
    if seen or depth == 0:
        return 1
    return walk(depth - 1) + walk(depth - 1)


def naps():
    while not seen:
        time.sleep(0.01)
    return "the naps ended"


def main(way, handler):
    if handler == "python":
        signal.signal(signal.SIGUSR1, note)
        signal.signal(signal.SIGUSR2, stop)
    elif handler == "installed":
        signal.signal(signal.SIGINT, signal.default_int_handler)
    print("SIGINT:", named(signal.getsignal(signal.SIGINT)))
    print("ready", flush=True)
    try:
        if way == "loop":
            print(spin())
        elif way == "recursion":
            print("the recursion ended:", walk(64) > 0)
        elif way == "naps":
            print(naps())
        elif way == "sleep":
            time.sleep(600)
            print("slept to the end")
        elif way == "read":
            print("read", os.read(0, 1))
        elif way == "itself":
            print("raise_signal returned", signal.raise_signal(signal.SIGINT))
    except Stop as e:
        print("stopped in the", way, e.args)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
"""


def _with_a_python_handler(command: list[str], way: str, tmp: str, ignored: Sequence[int] = ()) -> tuple[str, str, int]:
    """SIGUSR1 has a handler that notes and returns, SIGUSR2 one that raises. A loop, a recursion and a loop of naps end
    themselves once the handler has run; a sleep goes on after it (to its first deadline) and is left by SIGUSR2's exception;
    a read goes on after it and is given its byte."""
    with _Running([*command, way, "python"], tmp, ignored, stdin=way == "read") as running:
        said = running.line() + running.line()
        assert said.endswith("ready\n"), said
        if way in ("sleep", "read"):
            running.asleep()
        if ignored:
            running.send(signal.SIGINT)            # ignored: the system drops it, and the program must not have taken it over
        running.send(signal.SIGUSR1)
        assert running.line().startswith("handler 10 "), running.said       # the handler ran; what it was given is the caller's to compare
        if way == "sleep":
            running.asleep()
            running.send(signal.SIGUSR2)
        elif way == "read":
            running.asleep()
            running.write(b"x")
        return running.end()


def _with_the_default_handler(command: list[str], way: str, tmp: str, handler: str = "default") -> tuple[str, tuple[str, str], int, str]:
    """The last member is the whole traceback (masked as the harness masks it) where the signal finds the program at a known
    line, inside the sleep or the read; in a loop or a recursion it may be anywhere, and only the ends are compared."""
    with _Running([*command, way, handler], tmp, stdin=way == "read") as running:
        said = running.line() + running.line()
        assert said.endswith("ready\n"), said
        if way in ("sleep", "read"):
            running.asleep()
        running.send(signal.SIGINT)
        out, err, status = running.end()
    return out, _ends(err), status, mask_stderr(err) if way in ("sleep", "read") else ""


WITH_A_PYTHON_HANDLER = {
    "loop": ("SIGINT: default_int_handler\nready\nhandler 10 frame\nthe loop ended\n", "", 0),
    "recursion": ("SIGINT: default_int_handler\nready\nhandler 10 frame\nthe recursion ended: True\n", "", 0),
    "naps": ("SIGINT: default_int_handler\nready\nhandler 10 frame\nthe naps ended\n", "", 0),
    "sleep": ("SIGINT: default_int_handler\nready\nhandler 10 frame\nstopped in the sleep (12,)\n", "", 0),
    "read": ("SIGINT: default_int_handler\nready\nhandler 10 frame\nread b'x'\n", "", 0),
}


def test_a_signal_from_outside_runs_its_python_handler() -> None:
    """Where generated code looks (a loop's turn, a function's entry) and where the runtime does (a sleep and a read that
    the signal interrupts: the handler runs inside the call, which then goes on)."""
    if shutil.which("g++") is None:
        return
    with tempfile.TemporaryDirectory() as tmp:
        cpython, compiled = _two(WAITING, tmp)
        for way, expected in WITH_A_PYTHON_HANDLER.items():
            ref = _with_a_python_handler(cpython, way, tmp)
            got = _with_a_python_handler(compiled, way, tmp)
            assert ref == expected, (way, ref)
            assert got == ref, (way, got)


SIGINT_FOUND_IT_WAITING = {
    "sleep": 'Traceback (most recent call last):\n  File "prog.py", line 73, in <module>\n  File "prog.py", line 62, in main\nKeyboardInterrupt\n',
    "read": 'Traceback (most recent call last):\n  File "prog.py", line 73, in <module>\n  File "prog.py", line 65, in main\nKeyboardInterrupt\n',
}


def test_sigint_from_outside_is_a_keyboard_interrupt_and_the_process_dies_of_sigint() -> None:
    """The default handler for SIGINT (installed at start when SIGINT was at its default): KeyboardInterrupt in the loop, in
    the recursion, out of the sleep and out of the read; nobody catches it, so the traceback ends with its name and the
    process, having reported and flushed, sets SIGINT to its default and signals itself: a parent sees -2 (a shell 130)."""
    if shutil.which("g++") is None:
        return
    with tempfile.TemporaryDirectory() as tmp:
        cpython, compiled = _two(WAITING, tmp)
        for way in ("loop", "recursion", "naps", "sleep", "read"):
            ref = _with_the_default_handler(cpython, way, tmp)
            got = _with_the_default_handler(compiled, way, tmp)
            assert ref[:3] == ("SIGINT: default_int_handler\nready\n", ("Traceback (most recent call last):", "KeyboardInterrupt"), -2), (way, ref)
            assert ref[3] == SIGINT_FOUND_IT_WAITING.get(way, ""), (way, ref)
            assert got == ref, (way, got)


def test_started_with_sigint_ignored() -> None:
    """A program that finds SIGINT ignored leaves it so (signal_get_set_handlers installs default_int_handler only over
    SIG_DFL): getsignal says SIG_IGN, a SIGINT from outside is dropped by the system while the program computes and while it
    sleeps, and one it raises at itself returns."""
    if shutil.which("g++") is None:
        return
    ignored = (signal.SIGINT,)
    with tempfile.TemporaryDirectory() as tmp:
        cpython, compiled = _two(WAITING, tmp)
        for way, tail in (("loop", "handler 10 frame\nthe loop ended\n"), ("sleep", "handler 10 frame\nstopped in the sleep (12,)\n")):
            ref = _with_a_python_handler(cpython, way, tmp, ignored)
            got = _with_a_python_handler(compiled, way, tmp, ignored)
            assert ref == ("SIGINT: SIG_IGN\nready\n" + tail, "", 0), (way, ref)
            assert got == ref, (way, got)
        ref = _run([*cpython, "itself", "default"], tmp, ignored)
        got = _run([*compiled, "itself", "default"], tmp, ignored)
        assert ref == ("SIGINT: SIG_IGN\nready\nraise_signal returned None\n", "", 0), ref
        assert got == ref, got


# ---------------------------------------------------------------------------------------------------------------------------
# the ways a program ends by a signal
# ---------------------------------------------------------------------------------------------------------------------------

# "ready" goes to stderr, unbuffered, after the text that must still be in stdout's buffer when the signal comes
ENDING = r"""
import atexit
import os
import sys


class Kept:
    def __del__(self):
        print("a module's object is released")


kept = Kept()
atexit.register(print, "an exit hook ran")
sys.stdout.write("written, and still in the buffer\n")
os.write(2, b"ready\n")
while True:
    pass
"""


def _ended_by(command: list[str], number: int, tmp: str) -> tuple[str, tuple[str, str], int]:
    """stdout, the ends of what stderr holds after "ready", and the status."""
    with _Running(command, tmp) as running:
        assert running.line("stderr") == "ready\n", running.said
        running.send(number)
        out, err, status = running.end()
    return out, _ends(err.removeprefix("ready\n")), status


def _in_one_stream(command: list[str], tmp: str) -> tuple[list[str], int]:
    """SIGINT, with stderr written into stdout's pipe: the lines in the order they were written, but a traceback's frames
    and source lines (where the signal found the loop, which is not the test's), and the status."""
    with _Running(command, tmp, merged=True) as running:
        assert running.line() == "ready\n", running.said
        running.send(signal.SIGINT)
        out, _, status = running.end()
    return [line for line in out.splitlines() if not line.startswith("  ")], status


def test_a_signal_nobody_handles_ends_the_program_at_once() -> None:
    """SIGTERM, SIGHUP, SIGUSR1 and SIGALRM at their defaults: the system ends the process, no exit hook runs, no finaliser,
    and what stdout's buffer held is lost. (Neither CPython nor the runtime has a handler of its own for them.)"""
    if shutil.which("g++") is None:
        return
    with tempfile.TemporaryDirectory() as tmp:
        cpython, compiled = _two(ENDING, tmp)
        for number in (signal.SIGTERM, signal.SIGHUP, signal.SIGUSR1, signal.SIGALRM):
            ref = _ended_by(cpython, number, tmp)
            got = _ended_by(compiled, number, tmp)
            assert ref == ("", ("", ""), -int(number)), (number, ref)
            assert got == ref, (number, got)


def test_the_streams_are_flushed_before_the_process_dies_of_sigint() -> None:
    """SIGINT, nobody catching the KeyboardInterrupt: stdout flushed (Python/pythonrun.c:539, flush_io, before the error
    is handed back), the traceback (Modules/main.c:438-440), the exit hooks, stdout flushed, the modules' objects released
    and stdout flushed again, and only then the death by SIGINT (Py_RunMain: Py_FinalizeEx, then exit_sigint). The second
    run writes both streams into one pipe, which shows that order (RL-227 gave run_main the flush before the report)."""
    if shutil.which("g++") is None:
        return
    with tempfile.TemporaryDirectory() as tmp:
        cpython, compiled = _two(ENDING, tmp)
        ref = _ended_by(cpython, signal.SIGINT, tmp)
        got = _ended_by(compiled, signal.SIGINT, tmp)
        ref_order = _in_one_stream(cpython, tmp)
        got_order = _in_one_stream(compiled, tmp)
    assert ref == ("written, and still in the buffer\nan exit hook ran\na module's object is released\n",
                   ("Traceback (most recent call last):", "KeyboardInterrupt"), -2), ref
    assert got == ref, got
    assert ref_order == (["ready", "written, and still in the buffer", "Traceback (most recent call last):", "KeyboardInterrupt",
                          "an exit hook ran", "a module's object is released"], -2), ref_order
    assert got_order == ref_order, got_order


UNCAUGHT = r"""
import atexit
import signal
import sys


class Kept:
    def __del__(self):
        print("a module's object is released")


class Mine(KeyboardInterrupt):
    pass


def quiet(kind, value, tb):
    print("the hook was given", kind.__name__, value.args, tb is None)


def main(way):
    try:
        if way == "bare":
            raise KeyboardInterrupt
        if way == "with arguments":
            raise KeyboardInterrupt("why", 2)
        if way == "a subclass":
            raise Mine("mine")
        if way == "raise_signal":
            signal.raise_signal(signal.SIGINT)
        if way == "the hook replaced":
            sys.excepthook = quiet
            raise KeyboardInterrupt("unseen")
        if way == "SIGINT ignored by the program":
            signal.signal(signal.SIGINT, signal.SIG_IGN)
            raise KeyboardInterrupt
        if way == "SIGINT handled by the program":
            signal.signal(signal.SIGINT, lambda signum, frame: print("not called"))
            raise KeyboardInterrupt
        if way == "SIGINT blocked":
            signal.pthread_sigmask(signal.SIG_BLOCK, [signal.SIGINT])
            raise KeyboardInterrupt
        if way == "in an exit hook":
            atexit.register(signal.raise_signal, signal.SIGINT)
        if way == "caught":
            try:
                signal.raise_signal(signal.SIGINT)
            except KeyboardInterrupt as e:
                print("caught", type(e).__name__, e.args, e.__context__, e.__cause__)
        if way == "SystemExit while it is handled":
            try:
                raise KeyboardInterrupt
            except KeyboardInterrupt:
                sys.exit(5)
    finally:
        print("finally ran")


# (a hook of the program's own in sys.excepthook holds __main__'s namespace until the sys module is cleared, and a print
# then has no sys.stdout and says nothing: not this test's matter, so that row has no object to finalise)
kept = None if sys.argv[1] == "the hook replaced" else Kept()
atexit.register(print, "an exit hook ran")
print("written, and still in the buffer")
if __name__ == "__main__":
    main(sys.argv[1])
"""

FLUSHED = "written, and still in the buffer\nfinally ran\nan exit hook ran\na module's object is released\n"
UNCAUGHT_WAYS: dict[str, tuple[str, str, int]] = {
    "bare": (FLUSHED, 'Traceback (most recent call last):\n  File "prog.py", line 64, in <module>\n  File "prog.py", line 23, in main\nKeyboardInterrupt\n', -2),
    "with arguments": (FLUSHED, 'Traceback (most recent call last):\n  File "prog.py", line 64, in <module>\n  File "prog.py", line 25, in main\n'
                                "KeyboardInterrupt: ('why', 2)\n", -2),
    "a subclass": (FLUSHED, 'Traceback (most recent call last):\n  File "prog.py", line 64, in <module>\n  File "prog.py", line 27, in main\nMine: mine\n', -2),
    "raise_signal": (FLUSHED, 'Traceback (most recent call last):\n  File "prog.py", line 64, in <module>\n  File "prog.py", line 29, in main\nKeyboardInterrupt\n', -2),
    # sys.excepthook is asked and prints what it likes; the process dies of SIGINT all the same
    "the hook replaced": ("written, and still in the buffer\nfinally ran\nthe hook was given KeyboardInterrupt ('unseen',) False\nan exit hook ran\n", "", -2),
    # whatever the program made of SIGINT, the end puts it back to its default first
    "SIGINT ignored by the program": (FLUSHED, 'Traceback (most recent call last):\n  File "prog.py", line 64, in <module>\n  File "prog.py", line 35, in main\nKeyboardInterrupt\n', -2),
    "SIGINT handled by the program": (FLUSHED, 'Traceback (most recent call last):\n  File "prog.py", line 64, in <module>\n  File "prog.py", line 38, in main\nKeyboardInterrupt\n', -2),
    # blocked, the signal the process sends itself stays pending, kill returns, and the status is 128 + SIGINT
    "SIGINT blocked": (FLUSHED, 'Traceback (most recent call last):\n  File "prog.py", line 64, in <module>\n  File "prog.py", line 41, in main\nKeyboardInterrupt\n', 130),
    # an exit hook's KeyboardInterrupt is reported and ignored like any other exception of a hook (no frame: no traceback)
    "in an exit hook": (FLUSHED, "Exception ignored in atexit callback <built-in function raise_signal>:\nKeyboardInterrupt\n", 0),
    "caught": ("written, and still in the buffer\ncaught KeyboardInterrupt () None None\nfinally ran\nan exit hook ran\na module's object is released\n", "", 0),
    "SystemExit while it is handled": (FLUSHED, "", 5),
}


def test_an_uncaught_keyboard_interrupt_ends_the_process_by_sigint() -> None:
    """Whoever raised it (the program by hand, a subclass, the default handler), whatever sys.excepthook is and whatever the
    program did to SIGINT: once everything is reported, run and flushed, SIGINT is set to its default and the process signals
    itself (Modules/main.c exit_sigint; pythonrun.c notes the KeyboardInterrupt before the hook is asked). With SIGINT
    blocked the signal stays pending and the status is 128 + SIGINT. Caught, or raised in an exit hook, it ends nothing."""
    if shutil.which("g++") is None:
        return
    with tempfile.TemporaryDirectory() as tmp:
        cpython, compiled = _two(UNCAUGHT, tmp)
        for way, expected in UNCAUGHT_WAYS.items():
            ref = _run([*cpython, way], tmp)
            got = _run([*compiled, way], tmp)
            assert ref == expected, (way, ref)
            assert got == ref, (way, got)
        # started with SIGINT ignored: an uncaught KeyboardInterrupt still ends the process by SIGINT
        ref = _run([*cpython, "bare"], tmp, (signal.SIGINT,))
        got = _run([*compiled, "bare"], tmp, (signal.SIGINT,))
        assert ref == UNCAUGHT_WAYS["bare"], ref
        assert got == ref, got


# ---------------------------------------------------------------------------------------------------------------------------
# a signal that arrives after the program's last look: the look after the main module, and the first exit flush before it
# ---------------------------------------------------------------------------------------------------------------------------

# The last thing the program does is compare two lists of 200 million places in all: no call, no loop and no function's
# entry, so neither CPython's evaluation loop nor generated code looks again, and a timer set 10 ms ahead fires inside it
# (0.28 s under CPython here; a compiled program must take longer than 10 ms over it too, see expectations.md). Then the
# module ends, or raises a SystemExit made before the timer was set (`raise exc` makes no call, so it does not look).
# What is left is the program's end: CPython flushes the streams (Python/pythonrun.c:539 and 1353-1375, flush_io: an error
# there is cleared; the buffered writer advances its position after its raw write and only then looks for signals,
# Modules/_io/bufferedio.c:2051-2058), reports a SystemExit by handing its status back (Modules/main.c:109-128), and then
# looks itself (Modules/main.c:757, pymain_check_signals: route C) before the exit hooks run. The handler and the exit hook
# write to stdout's descriptor, so that stdout shows whether the buffered text went out before the handler ran or only with
# the last flush, after the hooks (a look before the raw write would give that).
# Not here, and a difference the runtime has: with any other uncaught exception CPython's default sys.excepthook is Python
# code (Lib/traceback.py), so a handler still owed runs INSIDE the report, given a frame (_find_and_load, or
# _print_exception_bltin once traceback is imported), before the traceback is printed, and the status stays 1 (or -2)
# whatever the handler raises; the runtime's report is C++ and its look comes after it, with None.
LATE = r"""
import atexit
import os
import signal
import sys

way, buffered, ending = sys.argv[1], sys.argv[2] == "buffered", sys.argv[3]


def late(signum, frame):
    os.write(1, ("the handler ran, frame is None: " + str(frame is None) + "\n").encode())
    if way == "exits":
        raise SystemExit(9)
    if way == "raises":
        raise ValueError("late")


signal.signal(signal.SIGALRM, signal.default_int_handler if way == "default_int_handler" else late)
atexit.register(os.write, 1, b"an exit hook ran\n")
row, other = [0] * 1000000, [0] * 1000000
a, b = [row] * 200, [other] * 200
exc = SystemExit(3)
if buffered:
    sys.stdout.write("written, and still in the buffer\n")
signal.setitimer(signal.ITIMER_REAL, 0.01)
a == b
if ending == "SystemExit":
    raise exc
"""

RAN = "the handler ran, frame is None: True\nan exit hook ran\n"
WRITTEN = "written, and still in the buffer\n"
LATE_RAISED = 'Traceback (most recent call last):\n  File "prog.py", line 15, in late\nValueError: late\n'
LATE_WAYS: dict[tuple[str, str, str], tuple[str, str, int]] = {
    # nothing in the buffer: the handler runs at the look after the main module, with no frame, before the exit hooks; what
    # it raises is reported as an uncaught exception is, and its status is the program's
    ("returns", "empty", "ends"): (RAN, "", 0),
    ("exits", "empty", "ends"): (RAN, "", 9),
    ("raises", "empty", "ends"): (RAN, LATE_RAISED, 1),
    ("default_int_handler", "empty", "ends"): ("an exit hook ran\n", "KeyboardInterrupt\n", -2),
    # text in stdout's buffer: the flush that comes first writes it, the buffered writer looks after its raw write, the
    # handler runs there, and what it raises is cleared with the flush's error: no word of it, status 0
    ("returns", "buffered", "ends"): (WRITTEN + RAN, "", 0),
    ("exits", "buffered", "ends"): (WRITTEN + RAN, "", 0),
    ("raises", "buffered", "ends"): (WRITTEN + RAN, "", 0),
    ("default_int_handler", "buffered", "ends"): (WRITTEN + "an exit hook ran\n", "", 0),
    # the module raised SystemExit(3): the look after the main module comes after its report too, and what the handler
    # raises there replaces the status
    ("returns", "empty", "SystemExit"): (RAN, "", 3),
    ("exits", "empty", "SystemExit"): (RAN, "", 9),
    ("raises", "empty", "SystemExit"): (RAN, LATE_RAISED, 1),
    ("default_int_handler", "empty", "SystemExit"): ("an exit hook ran\n", "KeyboardInterrupt\n", -2),
    # ... and the flush before the report found the handler, whose exception it swallowed: 3
    ("returns", "buffered", "SystemExit"): (WRITTEN + RAN, "", 3),
    ("exits", "buffered", "SystemExit"): (WRITTEN + RAN, "", 3),
    ("raises", "buffered", "SystemExit"): (WRITTEN + RAN, "", 3),
    ("default_int_handler", "buffered", "SystemExit"): (WRITTEN + "an exit hook ran\n", "", 3),
}


def test_a_signal_after_the_last_look_is_handled_when_the_program_has_ended() -> None:
    """The look after the main module, after a module that ended and after one that raised SystemExit (the exit hooks
    still run after a handler's SystemExit, whose status is the program's), and the flush before it, which writes the
    buffered text before it runs the handler and swallows what the handler raises."""
    if shutil.which("g++") is None:
        return
    with tempfile.TemporaryDirectory() as tmp:
        cpython, compiled = _two(LATE, tmp)
        for (way, buffer, ending), expected in LATE_WAYS.items():
            ref = _run([*cpython, way, buffer, ending], tmp)
            got = _run([*compiled, way, buffer, ending], tmp)
            assert ref == expected, (way, buffer, ending, ref)
            assert got == ref, (way, buffer, ending, got)


# ---------------------------------------------------------------------------------------------------------------------------
# the end of signal handling at exit (_PySignal_Fini): after the exit hooks and the first flush, before the modules go
# ---------------------------------------------------------------------------------------------------------------------------

# Finalisers take what they need as defaults: at the modules' end the program's own globals are already None.
# The numbers are 2 (SIGINT, default_int_handler), 10 (SIGUSR1, the handler object), 12 (SIGUSR2, ignored), 15 (SIGTERM).
HANDLERS_AT_EXIT = r"""
import _signal
import atexit
import signal
import sys

NUMBERS = (2, 10, 12, 15)


class Handler:
    def __call__(self, signum, frame):
        pass

    def __del__(self, getsignal=_signal.getsignal):
        print("the handler object is released; getsignal:", [getsignal(n) for n in NUMBERS])


class Kept:
    def __del__(self, getsignal=_signal.getsignal, raise_signal=_signal.raise_signal, way=sys.argv[1]):
        print("a module's object is released; getsignal:", [getsignal(n) for n in NUMBERS])
        if way == "raises at the end":
            raise_signal(10)
            print("not reached")


def hook():
    table = [_signal.getsignal(n) for n in NUMBERS]
    print("an exit hook; getsignal:", [type(h).__name__ if callable(h) else h for h in table])


kept = Kept()
signal.signal(signal.SIGUSR1, Handler())
signal.signal(signal.SIGUSR2, signal.SIG_IGN)
atexit.register(hook)
print("the program ends")
"""


def test_what_a_handler_objects_finaliser_sees_at_exit() -> None:
    """The exit hooks still see the table. Then each slot is emptied before its object is released, in the signals' order:
    the handler object of signal 10, held by the table alone, is finalised when 1 to 10 already read None and 12 and 15 are
    still what they were; the modules' objects, later, read None for every signal."""
    if shutil.which("g++") is None:
        return
    with tempfile.TemporaryDirectory() as tmp:
        cpython, compiled = _two(HANDLERS_AT_EXIT, tmp)
        ref = _run([*cpython, "ends"], tmp)
        got = _run([*compiled, "ends"], tmp)
    assert ref == ("the program ends\nan exit hook; getsignal: ['builtin_function_or_method', 'Handler', 1, 0]\n"
                   "the handler object is released; getsignal: [None, None, 1, 0]\n"
                   "a module's object is released; getsignal: [None, None, None, None]\n", "", 0), ref
    assert got == ref, got


def test_a_signal_that_had_a_handler_ends_the_program_once_handling_is_over() -> None:
    """A signal that had a Python handler is back at its default when the modules go: raised there it ends the process,
    and what was printed after the exit flush is lost with stdout's buffer."""
    if shutil.which("g++") is None:
        return
    with tempfile.TemporaryDirectory() as tmp:
        cpython, compiled = _two(HANDLERS_AT_EXIT, tmp)
        ref = _run([*cpython, "raises at the end"], tmp)
        got = _run([*compiled, "raises at the end"], tmp)
    assert ref == ("the program ends\nan exit hook; getsignal: ['builtin_function_or_method', 'Handler', 1, 0]\n", "", -10), ref
    assert got == ref, got


# ---------------------------------------------------------------------------------------------------------------------------
# what a program started by os.posix_spawn inherits
# ---------------------------------------------------------------------------------------------------------------------------

# argv: "parent" and the child's command, or "child". The parent has a Python handler for SIGUSR1 and for SIGHUP, ignores
# SIGUSR2, blocks SIGTERM and SIGHUP and has SIGTERM pending. The child reads its table, its mask and what is pending.
INHERITS = r"""
import os
import signal
import sys


def table():
    names = []
    for number in (signal.SIGHUP, signal.SIGINT, signal.SIGUSR1, signal.SIGUSR2, signal.SIGPIPE, signal.SIGTERM, signal.SIGXFSZ):
        handler = signal.getsignal(number)
        names.append(number.name + "=" + (handler.name if isinstance(handler, signal.Handlers) else handler.__name__))
    return " ".join(names)


def numbers(signals):
    return sorted(int(number) for number in signals)


def child():
    print("child:", table(), "| mask", numbers(signal.pthread_sigmask(signal.SIG_BLOCK, [])), "| pending", numbers(signal.sigpending()))


def note(signum, frame):
    pass


def parent(command):
    signal.signal(signal.SIGUSR1, note)
    signal.signal(signal.SIGHUP, note)
    signal.signal(signal.SIGUSR2, signal.SIG_IGN)
    signal.pthread_sigmask(signal.SIG_BLOCK, [signal.SIGTERM, signal.SIGHUP])
    signal.raise_signal(signal.SIGTERM)
    print("parent:", table(), "| mask", numbers(signal.pthread_sigmask(signal.SIG_BLOCK, [])), "| pending", numbers(signal.sigpending()), flush=True)
    pid = os.posix_spawn(command[0], command, os.environ)
    print("the child's status:", os.waitstatus_to_exitcode(os.waitpid(pid, 0)[1]))
    print("parent, afterwards: pending", numbers(signal.sigpending()))
    signal.signal(signal.SIGTERM, signal.SIG_IGN)       # the pending SIGTERM is dropped, not delivered
    signal.pthread_sigmask(signal.SIG_SETMASK, [])


if __name__ == "__main__":
    if sys.argv[1] == "child":
        child()
    else:
        parent(sys.argv[2:])
"""

INHERITED = ("parent: SIGHUP=note SIGINT=default_int_handler SIGUSR1=note SIGUSR2=SIG_IGN SIGPIPE=SIG_IGN SIGTERM=SIG_DFL SIGXFSZ=SIG_IGN | mask [1, 15] | pending [15]\n"
             "child: SIGHUP=SIG_DFL SIGINT=default_int_handler SIGUSR1=SIG_DFL SIGUSR2=SIG_IGN SIGPIPE=SIG_IGN SIGTERM=SIG_DFL SIGXFSZ=SIG_IGN | mask [1, 15] | pending []\n"
             "the child's status: 0\nparent, afterwards: pending [15]\n", "", 0)


def test_a_spawned_program_inherits_what_is_ignored_and_the_mask_but_no_handler() -> None:
    """exec puts a handled signal back to its default and keeps what is ignored and the mask; what is pending stays with the
    parent. All four pairs of parent and child, CPython's and compiled, say the same: so the runtime neither blocks nor
    ignores anything on its own account that a child would see (os.posix_spawn passes nothing on its own, as CPython's
    does not: _Py_RestoreSignals is subprocess's), and a compiled child reads at its start what CPython reads
    (signal_get_set_handlers), taking SIGINT, which arrives at its default, for default_int_handler."""
    if shutil.which("g++") is None:
        return
    with tempfile.TemporaryDirectory() as tmp:
        cpython, compiled = _two(INHERITS, tmp)
        for parent in (cpython, compiled):
            for child in (cpython, compiled):
                outcome = _run([*parent, "parent", *child, "child"], tmp)
                assert outcome == INHERITED, (parent, child, outcome)


# ---------------------------------------------------------------------------------------------------------------------------
# the words of every refusal of the _signal functions (the cases print the classes only)
# ---------------------------------------------------------------------------------------------------------------------------

# Every function's argument parsing in the clinic's order, then its own checks in the C's order (Modules/signalmodule.c and
# Modules/clinic/signalmodule.c.h): a row says which check comes first where two would refuse. Nothing here sends a signal
# that could end the program: raise_signal is given only numbers the C library refuses (32 and 33 among them; True would be
# SIGHUP), pthread_kill only this thread's id or an id that warns before the call, and no wait is entered (an empty set
# would wait for ever). Warnings are errors, so that their words are compared too.
REFUSALS = r"""
import _signal
import _thread
import os
import warnings

warnings.simplefilter("error")          # a warning's words are compared as an exception's are
counts = {}


def show(name, g):
    counts[name] = counts.get(name, 0) + 1
    try:
        said = repr(g())
    except BaseException as e:
        said = type(e).__name__ + ": " + str(e)
    print(name, counts[name], "->", said)


class Index:
    def __init__(self, n):
        self.n = n

    def __index__(self):
        return self.n


class Number(int):
    pass


class Truth:
    def __bool__(self):
        raise RuntimeError("asked for its truth")


def h(signum, frame):
    pass


me = _thread.get_ident()
r, w = os.pipe()
os.dup2(w, 100)                          # a blocking descriptor with a number of its own choosing
os.close(r)
os.close(w)
big = 2**40

for g in (lambda: _signal.default_int_handler(), lambda: _signal.default_int_handler(2), lambda: _signal.default_int_handler(2, None, 3),
          lambda: _signal.default_int_handler("x", None), lambda: _signal.default_int_handler(2.0, None), lambda: _signal.default_int_handler(big, None),
          lambda: _signal.default_int_handler(signalnum=2, frame=None), lambda: _signal.default_int_handler(2, frame=None),
          lambda: _signal.default_int_handler(2, None), lambda: _signal.default_int_handler(Index(-5), "anything"), lambda: _signal.default_int_handler(True, 1.5)):
    show("default_int_handler", g)
for g in (lambda: _signal.alarm(), lambda: _signal.alarm(1, 2), lambda: _signal.alarm("x"), lambda: _signal.alarm(1.5), lambda: _signal.alarm(None),
          lambda: _signal.alarm(2**31), lambda: _signal.alarm(-2**31 - 1), lambda: _signal.alarm(seconds=1)):
    show("alarm", g)
for g in (lambda: _signal.setitimer(), lambda: _signal.setitimer(0), lambda: _signal.setitimer(0, 1, 2, 3), lambda: _signal.setitimer("a", 1),
          lambda: _signal.setitimer(1.5, 1), lambda: _signal.setitimer(big, 1), lambda: _signal.setitimer(0, "b"), lambda: _signal.setitimer(0, None),
          lambda: _signal.setitimer(0, 1, None), lambda: _signal.setitimer(0, 1, "c"), lambda: _signal.setitimer(0, 1j), lambda: _signal.setitimer(0, float("nan")),
          lambda: _signal.setitimer(0, float("inf")), lambda: _signal.setitimer(0, 1e30), lambda: _signal.setitimer(0, big), lambda: _signal.setitimer(0, -2**70),
          lambda: _signal.setitimer(0, 1, float("nan")), lambda: _signal.setitimer(0, 1, big), lambda: _signal.setitimer(3, "b"), lambda: _signal.setitimer("a", "b"),
          lambda: _signal.setitimer(3, 1), lambda: _signal.setitimer(-1, 1), lambda: _signal.setitimer(0, -1), lambda: _signal.setitimer(0, -0.5),
          lambda: _signal.setitimer(0, 1, -1), lambda: _signal.setitimer(which=0, seconds=1), lambda: _signal.setitimer(0, 1, interval=1)):
    show("setitimer", g)
for g in (lambda: _signal.getitimer(), lambda: _signal.getitimer(0, 1), lambda: _signal.getitimer("x"), lambda: _signal.getitimer(1.5), lambda: _signal.getitimer(big),
          lambda: _signal.getitimer(3), lambda: _signal.getitimer(-1), lambda: _signal.getitimer(which=0)):
    show("getitimer", g)
for g in (lambda: _signal.signal(), lambda: _signal.signal(10), lambda: _signal.signal(10, h, 3), lambda: _signal.signal("x", h), lambda: _signal.signal(1.5, h),
          lambda: _signal.signal(None, h), lambda: _signal.signal(big, h), lambda: _signal.signal(-big, 5), lambda: _signal.signal(0, h), lambda: _signal.signal(65, h),
          lambda: _signal.signal(-1, h), lambda: _signal.signal(65, 5), lambda: _signal.signal("x", 5), lambda: _signal.signal(10, 5), lambda: _signal.signal(10, None),
          lambda: _signal.signal(10, "SIG_IGN"), lambda: _signal.signal(10, True), lambda: _signal.signal(10, False), lambda: _signal.signal(10, 0.0),
          lambda: _signal.signal(10, Number(1)), lambda: _signal.signal(10, Index(1)), lambda: _signal.signal(10, 2), lambda: _signal.signal(10, -1),
          lambda: _signal.signal(9, 5), lambda: _signal.signal(9, h), lambda: _signal.signal(9, 0), lambda: _signal.signal(19, 1), lambda: _signal.signal(32, h),
          lambda: _signal.signal(33, 0), lambda: _signal.signal(signalnum=10, handler=h), lambda: _signal.signal(10, handler=h)):
    show("signal", g)
for g in (lambda: _signal.raise_signal(), lambda: _signal.raise_signal(1, 2), lambda: _signal.raise_signal("x"), lambda: _signal.raise_signal(1.5),
          lambda: _signal.raise_signal(None), lambda: _signal.raise_signal(big), lambda: _signal.raise_signal(-1), lambda: _signal.raise_signal(65),
          lambda: _signal.raise_signal(100), lambda: _signal.raise_signal(32), lambda: _signal.raise_signal(33), lambda: _signal.raise_signal(signalnum=0)):
    show("raise_signal", g)
for g in (lambda: _signal.strsignal(), lambda: _signal.strsignal(1, 2), lambda: _signal.strsignal("x"), lambda: _signal.strsignal(1.5), lambda: _signal.strsignal(big),
          lambda: _signal.strsignal(0), lambda: _signal.strsignal(65), lambda: _signal.strsignal(-1), lambda: _signal.strsignal(signalnum=1)):
    show("strsignal", g)
for g in (lambda: _signal.getsignal(), lambda: _signal.getsignal(1, 2), lambda: _signal.getsignal("x"), lambda: _signal.getsignal(1.5), lambda: _signal.getsignal(big),
          lambda: _signal.getsignal(0), lambda: _signal.getsignal(65), lambda: _signal.getsignal(-1), lambda: _signal.getsignal(signalnum=1)):
    show("getsignal", g)
for g in (lambda: _signal.set_wakeup_fd(), lambda: _signal.set_wakeup_fd(fd=-1), lambda: _signal.set_wakeup_fd(1, 2), lambda: _signal.set_wakeup_fd(1, 2, 3, 4, 5),
          lambda: _signal.set_wakeup_fd(-1, warn_on_full_buffer=1, x=2), lambda: _signal.set_wakeup_fd(-1, x=1), lambda: _signal.set_wakeup_fd(warn_on_full_buffer=True),
          lambda: _signal.set_wakeup_fd("a"), lambda: _signal.set_wakeup_fd(1.5), lambda: _signal.set_wakeup_fd(None), lambda: _signal.set_wakeup_fd(2**31),
          lambda: _signal.set_wakeup_fd(-2**70), lambda: _signal.set_wakeup_fd("a", warn_on_full_buffer=Truth()), lambda: _signal.set_wakeup_fd(-1, warn_on_full_buffer=Truth()),
          lambda: _signal.set_wakeup_fd(-2), lambda: _signal.set_wakeup_fd(-100), lambda: _signal.set_wakeup_fd(9999), lambda: _signal.set_wakeup_fd(w),
          lambda: _signal.set_wakeup_fd(100), lambda: _signal.set_wakeup_fd(100, warn_on_full_buffer=False)):
    show("set_wakeup_fd", g)
for g in (lambda: _signal.siginterrupt(), lambda: _signal.siginterrupt(10), lambda: _signal.siginterrupt(10, 1, 2), lambda: _signal.siginterrupt("a", 1),
          lambda: _signal.siginterrupt(10, "a"), lambda: _signal.siginterrupt(10, 1.5), lambda: _signal.siginterrupt(10, None), lambda: _signal.siginterrupt("a", 65),
          lambda: _signal.siginterrupt(65, "a"), lambda: _signal.siginterrupt(big, 1), lambda: _signal.siginterrupt(10, big), lambda: _signal.siginterrupt(0, 1),
          lambda: _signal.siginterrupt(65, 0), lambda: _signal.siginterrupt(-1, 0), lambda: _signal.siginterrupt(9, 1), lambda: _signal.siginterrupt(19, 0),
          lambda: _signal.siginterrupt(32, 0), lambda: _signal.siginterrupt(signalnum=10, flag=1)):
    show("siginterrupt", g)
for g in (lambda: _signal.pause(1), lambda: _signal.pause(x=1)):
    show("pause", g)
for g in (lambda: _signal.pidfd_send_signal(), lambda: _signal.pidfd_send_signal(1), lambda: _signal.pidfd_send_signal(1, 2, 3, 4, 5), lambda: _signal.pidfd_send_signal("a", 0),
          lambda: _signal.pidfd_send_signal(0, "a"), lambda: _signal.pidfd_send_signal(0, 0, None, "a"), lambda: _signal.pidfd_send_signal(big, 0),
          lambda: _signal.pidfd_send_signal(0, big), lambda: _signal.pidfd_send_signal(0, 0, None, big), lambda: _signal.pidfd_send_signal(0, 0, 5),
          lambda: _signal.pidfd_send_signal(0, 0, 5, "x"), lambda: _signal.pidfd_send_signal("a", 0, 5), lambda: _signal.pidfd_send_signal(-1, 0),
          lambda: _signal.pidfd_send_signal(9999, 0), lambda: _signal.pidfd_send_signal(100, 0), lambda: _signal.pidfd_send_signal(pidfd=1, signalnum=0),
          lambda: _signal.pidfd_send_signal(1, 0, siginfo=None)):
    show("pidfd_send_signal", g)
for g in (lambda: _signal.pthread_kill(), lambda: _signal.pthread_kill(me), lambda: _signal.pthread_kill(me, 0, 1), lambda: _signal.pthread_kill("x", 10),
          lambda: _signal.pthread_kill(None, 10), lambda: _signal.pthread_kill(1.5, 10), lambda: _signal.pthread_kill("x", "y"), lambda: _signal.pthread_kill(me, "x"),
          lambda: _signal.pthread_kill(me, 1.5), lambda: _signal.pthread_kill(me, big), lambda: _signal.pthread_kill(2**64, 0), lambda: _signal.pthread_kill(-2**63 - 1, 0),
          lambda: _signal.pthread_kill(2**64, "x"), lambda: _signal.pthread_kill(me, 65), lambda: _signal.pthread_kill(me, -1), lambda: _signal.pthread_kill(me, 32),
          lambda: _signal.pthread_kill(thread_id=me, signalnum=0), lambda: _signal.pthread_kill(me, signalnum=0)):
    show("pthread_kill", g)
for g in (lambda: _signal.pthread_sigmask(), lambda: _signal.pthread_sigmask(0), lambda: _signal.pthread_sigmask(0, [], 1), lambda: _signal.pthread_sigmask("a", []),
          lambda: _signal.pthread_sigmask(1.5, []), lambda: _signal.pthread_sigmask(big, []), lambda: _signal.pthread_sigmask("a", 5), lambda: _signal.pthread_sigmask(0, 5),
          lambda: _signal.pthread_sigmask(0, None), lambda: _signal.pthread_sigmask(0, [0]), lambda: _signal.pthread_sigmask(0, [65]), lambda: _signal.pthread_sigmask(0, [-1]),
          lambda: _signal.pthread_sigmask(0, [2**70]), lambda: _signal.pthread_sigmask(0, [-2**70]), lambda: _signal.pthread_sigmask(0, ["x"]),
          lambda: _signal.pthread_sigmask(0, [1.5]), lambda: _signal.pthread_sigmask(0, [None]), lambda: _signal.pthread_sigmask(0, "10"),
          lambda: _signal.pthread_sigmask(0, [10, 0]), lambda: _signal.pthread_sigmask(0, [32]), lambda: _signal.pthread_sigmask(0, [10, 33]),
          lambda: _signal.pthread_sigmask(99, [0]), lambda: _signal.pthread_sigmask(3, []), lambda: _signal.pthread_sigmask(-1, []), lambda: _signal.pthread_sigmask(99, [10]),
          lambda: _signal.pthread_sigmask(how=0, mask=[]), lambda: _signal.pthread_sigmask(0, mask=[])):
    show("pthread_sigmask", g)
for g in (lambda: _signal.sigpending(1), lambda: _signal.sigpending(x=1)):
    show("sigpending", g)
for g in (lambda: _signal.sigwait(), lambda: _signal.sigwait([10], 2), lambda: _signal.sigwait(5), lambda: _signal.sigwait([0]), lambda: _signal.sigwait([65]),
          lambda: _signal.sigwait(["x"]), lambda: _signal.sigwait([10, 32]), lambda: _signal.sigwait(sigset=[10])):
    show("sigwait", g)
for g in (lambda: _signal.sigwaitinfo(), lambda: _signal.sigwaitinfo([10], 2), lambda: _signal.sigwaitinfo(5), lambda: _signal.sigwaitinfo([0]), lambda: _signal.sigwaitinfo([65]),
          lambda: _signal.sigwaitinfo(["x"]), lambda: _signal.sigwaitinfo([10, 32]), lambda: _signal.sigwaitinfo(sigset=[10])):
    show("sigwaitinfo", g)
for g in (lambda: _signal.sigtimedwait(), lambda: _signal.sigtimedwait([10]), lambda: _signal.sigtimedwait([], 0, 1), lambda: _signal.sigtimedwait(5, 0),
          lambda: _signal.sigtimedwait(5, "x"), lambda: _signal.sigtimedwait([0], 0), lambda: _signal.sigtimedwait([0], "x"), lambda: _signal.sigtimedwait([33], 0),
          lambda: _signal.sigtimedwait([], "x"), lambda: _signal.sigtimedwait([], None), lambda: _signal.sigtimedwait([], 1j), lambda: _signal.sigtimedwait([], -1),
          lambda: _signal.sigtimedwait([], -0.001), lambda: _signal.sigtimedwait([], -1e-9), lambda: _signal.sigtimedwait([], float("nan")),
          lambda: _signal.sigtimedwait([], float("inf")), lambda: _signal.sigtimedwait([], 1e30), lambda: _signal.sigtimedwait([], big), lambda: _signal.sigtimedwait([], -2**70),
          lambda: _signal.sigtimedwait(sigset=[], timeout=0), lambda: _signal.sigtimedwait([], timeout=0)):
    show("sigtimedwait", g)
for g in (lambda: _signal.valid_signals(1), lambda: _signal.valid_signals(x=1)):
    show("valid_signals", g)

# nothing above changed anything: no timer runs, no signal is blocked or pending, no handler was put in, no descriptor is set
warnings.simplefilter("default")
print(_signal.getitimer(0), _signal.getitimer(1), _signal.getitimer(2), _signal.alarm(0), sorted(_signal.pthread_sigmask(0, [])), sorted(_signal.sigpending()),
      [_signal.getsignal(n) for n in (9, 10, 19)], _signal.getsignal(2) is _signal.default_int_handler, _signal.set_wakeup_fd(-1))
"""

# struct_siginfo (a struct sequence named signal.struct_siginfo, no base type) and ItimerError (an OSError of module signal)
THE_TWO_TYPES = r"""
import _signal
import signal


def m(g):
    try:
        return repr(g())
    except BaseException as e:
        return type(e).__name__ + ": " + str(e)


S, E = _signal.struct_siginfo, _signal.ItimerError
print(m(lambda: S()))
print(m(lambda: S(5)))
print(m(lambda: S((1, 2, 3))))
print(m(lambda: S(range(8))))
print(m(lambda: S(sequence=range(7))))
print(m(lambda: S(range(7), {})))
print(m(lambda: S(range(7), 5)))
print(m(lambda: S(range(7), x=1)))
print(m(lambda: type("Sub", (S,), {})))
print(m(lambda: setattr(S(range(7)), "si_signo", 5)))
print(m(lambda: S(range(7)).si_code), m(lambda: S(range(7)).nothing))
print(m(lambda: S(range(7))), S.__module__, S.__name__, S.__qualname__, S.n_fields, S.n_sequence_fields, S.n_unnamed_fields, S.__match_args__)
print(m(lambda: E()), m(lambda: E(22, "Invalid argument")), m(lambda: E(1, 2, 3)), m(lambda: E(x=1)), E.__module__, E.__name__, E.__qualname__, E.__mro__[1].__name__, E.__doc__)
print(str(E(22, "Invalid argument")), str(E(22, "words", "name")), E(2, "x").errno, E(2, "x").filename, type(E(2, "No such file")).__name__)
print(signal.ItimerError is E, signal.struct_siginfo is S)
"""


def test_the_words_of_every_refusal() -> None:
    _same(REFUSALS)


def test_what_the_two_types_refuse_and_say() -> None:
    _same(THE_TWO_TYPES)


def test_pthread_kill_to_another_thread_stops_by_name() -> None:
    """Design point 8's ruling. CPython hands any id to the C library's pthread_kill, which is undefined behaviour for one
    that is no thread's (a crash, at best), so there is nothing to compare with: only the compiled side is asserted. It
    stops with the facility's name before anything is sent, as test_posix.py's stops do."""
    if shutil.which("g++") is None:
        return
    with tempfile.TemporaryDirectory() as tmp:
        prog = Path(tmp, "prog.py")
        prog.write_text("import _signal\nprint('start')\nif __name__ == '__main__':\n    try:\n        _signal.pthread_kill(1, 0)\n"
                        "    except BaseException:\n        print('raised')\n", encoding="utf-8")
        got = subprocess.run([str(build(prog, "prog.py"))], stdin=subprocess.DEVNULL, capture_output=True, text=True, check=False, timeout=WAIT)
    assert (got.returncode, got.stdout) == (70, "start\n") and "not implemented" in got.stderr and "signal.pthread_kill" in got.stderr, got


# ---------------------------------------------------------------------------------------------------------------------------
# where the next look finds a signal left waiting, and a child's signals: rows the cases C-7-75 and C-7-76 leave out
# ---------------------------------------------------------------------------------------------------------------------------

# Deterministic under CPython, but each breaks a rule the cases keep. The "next look" rows leave a signal waiting behind a
# handler that raised (the cases never do), and hold only as long as nothing between the raise and the probe looks in
# CPython: no call of a built-in (CPython looks after it), no repr, str, print or int formatting (they call
# PyErr_CheckSignals). They need no clock, and they are the only way to show the look after a generator's yield by itself,
# that straight-line code does not look, where a loop's look is, that an inlined comprehension has no entry look, and the
# two notes (a Python handler that raised has taken the evaluation loop's note down at its own entry, so only a look of the
# kind PyErr_CheckSignals is finds what it left). The "a child" rows have a signal sent from outside the process. (Taken out
# of C-7-75 and C-7-76 when those cases were written.) Run with the argument "children", the program does only the last.
NEXT_LOOKS = r'''
import _signal
import _thread
import os
import signal
import sys
import time
import types
from collections.abc import Callable, Iterator

U1, HUP, INT, CHLD = signal.SIGUSR1, signal.SIGHUP, signal.SIGINT, signal.SIGCHLD

log: list[object] = []
hits = 0


def taken() -> list[object]:
    seen = list(log)
    log.clear()
    return seen


def note(signum: int, frame: types.FrameType | None) -> None:
    log.append(signum)


def other(signum: int, frame: types.FrameType | None) -> None:
    log.append(("other", signum))


def hit(signum: int, frame: types.FrameType | None) -> None:
    global hits
    hits += 1


class Stop(Exception):
    pass


def stops(signum: int, frame: types.FrameType | None) -> None:
    log.append(("stops", signum))
    raise Stop(signum)


def interrupted_with(pending: int) -> None:
    """SIGINT and another signal are pending and unblocked together: the handler Python has for SIGINT raises, and the other
    signal's handler is still owed. That handler is no Python function, so the note the program's own code looks at is
    still up: the next look that code makes finds the other signal."""
    signal.pthread_sigmask(signal.SIG_BLOCK, [INT, pending])
    signal.raise_signal(pending)
    signal.raise_signal(INT)
    try:
        signal.pthread_sigmask(signal.SIG_UNBLOCK, [INT, pending])
    except KeyboardInterrupt:
        pass


def marker() -> None:
    log.append("the function's body")


def guarded() -> str:
    try:
        return "the body ran"
    except Stop:
        return "caught inside the function"


def gen() -> Iterator[int]:
    log.append("the generator's body")
    yield 1
    log.append("after the yield")
    yield 2


def gen_guarded() -> Iterator[int]:
    try:
        yield 1
        log.append("after the yield")
    except Stop:
        log.append("caught inside the generator, around its yield")
    yield 2


def one_turn_for() -> None:
    global log
    interrupted_with(U1)
    for _ in (1,):
        log += ["the body"]
    log += ["after the loop"]


def one_turn_while() -> None:
    global log
    interrupted_with(U1)
    i = 0
    while i < 1:
        i += 1
        log += ["the body"]
    log += ["after the loop"]


def continued() -> None:
    global log
    interrupted_with(U1)
    for x in (1, 2):
        if x == 1:
            log += ["continue"]
            continue
        log += ["the second turn"]
    log += ["after the loop"]


def left_by_break() -> None:
    global log
    interrupted_with(U1)
    while True:
        log += ["the body"]
        break
    log += ["after the loop"]


def left_by_return() -> None:
    global log
    interrupted_with(U1)
    for _ in (1, 2):
        log += ["the body"]
        return
    log += ["not reached"]


def listcomp() -> list[int]:
    global hits
    hits = 0
    interrupted_with(U1)
    return [hits for _ in (1, 2, 3)]


def dictcomp() -> dict[int, int]:
    global hits
    hits = 0
    interrupted_with(U1)
    return {k: hits for k in (1, 2, 3)}


def genexpr() -> tuple[int, list[int]]:
    global hits
    hits = 0
    interrupted_with(U1)
    g = (hits for _ in (1, 2, 3))
    made = hits
    return made, [*g]


def a_class() -> tuple[int, int]:
    global hits
    hits = 0
    interrupted_with(U1)
    before = hits

    class C:
        x = hits
    return before, C.x


def a_lambda() -> tuple[int, int]:
    global hits
    hits = 0
    interrupted_with(U1)
    before = hits
    f = lambda: hits
    return before, f()


class Made:
    def __init__(self) -> None:
        self.x = hits


def an_init() -> tuple[int, int]:
    global hits
    hits = 0
    interrupted_with(U1)
    before = hits
    made = Made()
    return before, made.x


def what(call: Callable[[], object]) -> str:
    try:
        call()
        return "returned"
    except Exception as e:
        return type(e).__name__


def next_looks() -> None:
    global hits, log
    signal.signal(INT, signal.default_int_handler)
    signal.pthread_sigmask(signal.SIG_SETMASK, [])
    # straight-line code does not look; the next function's entry does, before its body
    signal.signal(U1, note)
    interrupted_with(U1)
    log += ["straight on"]          # no call is made here: a call of a built-in would look when it returns, in CPython
    marker()
    print("a function's entry:", taken())
    # a loop's first turn: the body has run once when the handler runs
    signal.signal(U1, hit)
    hits = 0
    interrupted_with(U1)
    seen: list[int] = []
    i = 0
    while i < 3:
        i += 1
        seen = [*seen, hits]
    print("a loop's turn:", seen)
    # ... the look of a loop's turn comes after the body, after its last turn too (before the condition or the iterator ends
    # the loop), and on continue; not when break or return leaves the loop: then the caller marks the return, and the entry
    # of the next function it calls finds the signal
    signal.signal(U1, note)
    turns = []
    for probe in (one_turn_for, one_turn_while, continued, left_by_break, left_by_return):
        probe()
        log += ["returned"]
        turns.append((probe.__name__, taken()))
    print("the last turn, continue, break, return:", turns)
    # an inlined comprehension has no entry of its own: its first look is its first turn's; a generator expression looks
    # when it first runs, not when it is made; a class body, a lambda and an __init__ the class calls look at their entry
    signal.signal(U1, hit)
    print("comprehensions:", listcomp(), dictcomp(), genexpr())
    print("a class body, a lambda, an __init__:", a_class(), a_lambda(), an_init())
    # a generator: making it does not look, its first run does, before its body; and so does going on after a yield
    signal.signal(U1, note)
    interrupted_with(U1)
    g = gen()
    made = [*log]
    first = next(g)
    started = taken()
    interrupted_with(U1)
    second = next(g)
    print("a generator:", made, first, started, second, taken())
    # where the exception of a handler that raises appears: before the function's own try, inside the try around a yield
    signal.signal(U1, stops)
    interrupted_with(U1)
    try:
        where = guarded()
    except Stop:
        where = "raised at the function's entry, before its own try"
    h = gen_guarded()
    next(h)
    interrupted_with(U1)
    after = next(h)
    print("a handler that raises:", where, after, taken())
    # ... and when the handler that raised was a Python function, the look at its own entry has taken the evaluation loop's
    # note down: the signal left waiting is found by no function's entry and no loop's turn, by none of the looks the runtime
    # makes when a call that waits is over (os.killpg, os.system, os.waitpid, a sleep, a write, a read, a lock's timed wait, a
    # free lock's acquire: CPython's look after a call tests the note), and by no refusal of a function that looks once it has its arguments
    # (Modules/signalmodule.c:503-530: _signal.signal checks the number and the handler, then looks, then asks the system;
    # raise_signal, os.kill, pthread_kill and pthread_sigmask look only when the system said yes); _signal.signal(9, ...)
    # finds it, and then fails
    child = os.posix_spawn("/bin/true", ["true"], {})
    held = _thread.allocate_lock()
    held.acquire()
    free = _thread.allocate_lock()
    r, w = os.pipe()
    signal.signal(HUP, stops)
    signal.signal(U1, note)
    signal.pthread_sigmask(signal.SIG_BLOCK, [HUP, U1])
    signal.raise_signal(U1)
    signal.raise_signal(HUP)
    try:
        signal.pthread_sigmask(signal.SIG_UNBLOCK, [HUP, U1])
    except Stop:
        pass
    marker()
    i = 0
    while i < 3:
        i += 1
    log.append("after a call and three turns")
    os.killpg(os.getpgrp(), 0)
    os.system("true")
    os.waitpid(child, 0)
    time.sleep(0)
    time.sleep(0.001)
    os.write(w, b"x")
    os.read(r, 1)
    held.acquire(True, 0.001)
    free.acquire()
    log.append("after the calls that wait")
    refused = [what(lambda: _signal.signal(U1, 5)), what(lambda: _signal.signal(65, note)), what(lambda: _signal.raise_signal(32)),
               what(lambda: os.kill(2**22 + 1, 0)), what(lambda: _signal.pthread_kill(_thread.get_ident(), 65)),
               what(lambda: _signal.pthread_sigmask(99, [])), what(lambda: _signal.siginterrupt(9, 1))]
    log.append("after the refusals")
    refused.append(what(lambda: _signal.signal(9, note)))
    log.append("after _signal.signal(9, note)")
    os.close(r)
    os.close(w)
    print("left waiting by a Python handler that raised:", taken(), refused)
    # signal.signal looks before it changes anything: a handler still owed runs first, the old one; if it raises, nothing
    # is installed. (The module underneath is called, since the signal module's own function would look where it starts.)
    signal.signal(HUP, signal.SIG_DFL)
    signal.signal(U1, note)
    interrupted_with(U1)
    was = _signal.signal(U1, other)
    first_old = (was is note, taken())
    signal.signal(U1, stops)
    interrupted_with(U1)
    try:
        _signal.signal(U1, other)
        log.append("installed")
    except Stop:
        log.append("signal.signal let the old handler's exception out")
    print("signal.signal with a handler still owed:", first_old, taken(), _signal.getsignal(U1) is stops)
    signal.signal(U1, signal.SIG_DFL)


def children() -> None:
    # a child: its signal to this program, and SIGCHLD when it ends, have been handled when the call that waits returns
    signal.signal(U1, note)
    signal.signal(CHLD, note)
    sys.stdout.flush()
    status = os.system("kill -USR1 $PPID")
    log.append("os.system returned")
    by_system = (status, taken())
    pid = os.posix_spawn("/bin/sh", ["sh", "-c", "kill -USR1 $PPID; exit 3"], {})
    got = os.waitpid(pid, 0)
    log.append("waitpid returned")
    by_waitpid = (got[0] == pid, got[1], taken())
    signal.signal(U1, signal.SIG_DFL)
    pid = os.posix_spawn("/bin/sh", ["sh", "-c", "exit 4"], {})
    got = os.wait()
    log.append("wait returned")
    print("a child:", by_system, by_waitpid, (got[0] == pid, got[1], taken()))
    signal.signal(CHLD, signal.SIG_DFL)


if __name__ == "__main__":
    if sys.argv[1:] != ["children"]:
        next_looks()
    children()
'''

CHILDREN = "a child: (0, [10, 17, 'os.system returned']) (True, 768, [10, 17, 'waitpid returned']) (True, 1024, [17, 'wait returned'])\n"
NEXT_LOOKED = (
    'a function\'s entry: [\'straight on\', 10, "the function\'s body"]\n'
    "a loop's turn: [0, 1, 1]\n"
    "the last turn, continue, break, return: [('one_turn_for', ['the body', 10, 'after the loop', 'returned']), "
    "('one_turn_while', ['the body', 10, 'after the loop', 'returned']), ('continued', ['continue', 10, 'the second turn', 'after the loop', 'returned']), "
    "('left_by_break', ['the body', 'after the loop', 'returned', 10]), ('left_by_return', ['the body', 'returned', 10])]\n"
    "comprehensions: [0, 1, 1] {1: 0, 2: 1, 3: 1} (0, [1, 1, 1])\n"
    "a class body, a lambda, an __init__: (0, 1) (0, 1) (0, 1)\n"
    'a generator: [] 1 [10, "the generator\'s body"] 2 [10, \'after the yield\']\n'
    "a handler that raises: raised at the function's entry, before its own try 2 [('stops', 10), ('stops', 10), 'caught inside the generator, around its yield']\n"
    'left waiting by a Python handler that raised: [(\'stops\', 1), "the function\'s body", \'after a call and three turns\', \'after the calls that wait\', '
    "'after the refusals', 10, 'after _signal.signal(9, note)'] ['TypeError', 'ValueError', 'OSError', 'ProcessLookupError', 'OSError', 'OSError', 'OSError', 'OSError']\n"
    'signal.signal with a handler still owed: (True, [10]) [(\'stops\', 10), "signal.signal let the old handler\'s exception out"] True\n'
    + CHILDREN
)


def test_where_the_next_look_finds_a_signal_left_waiting() -> None:
    """A function's entry, a loop's turn (after the body, the last turn's too, and on continue; not on break or return), a
    generator's first run and its going on after a yield, a class body, a lambda and an __init__ look; making a generator,
    an inlined comprehension's start and straight-line code do not; a handler's exception appears where the look is
    (before a function's own try, inside a generator's try around its yield); what a Python handler that raised leaves
    waiting is found by no look of generated code and by no look of the runtime's at the end of a call, only by a look of
    the kind PyErr_CheckSignals is, and signal.signal runs a handler still owed before it changes anything, after its own
    checks. Then a child that signals the program: handled when os.system, os.waitpid and os.wait return, with SIGCHLD after
    it."""
    if shutil.which("g++") is None:
        return
    with tempfile.TemporaryDirectory() as tmp:
        cpython, compiled = _two(NEXT_LOOKS, tmp)
        ref = _run(cpython, tmp)
        got = _run(compiled, tmp)
    assert ref == (NEXT_LOOKED, "", 0), ref
    assert got == ref, got


# A handler owed when a call that waits begins: SIGINT's default_int_handler raised in the call that unblocked both signals,
# and since that handler is no Python function the note the evaluation loop looks at is still up. CPython makes the call
# first and runs the handler at its look after the call (Python/bytecodes.c:4457, CALL's _CHECK_PERIODIC_AT_END): none of
# these calls looks before it waits (time.sleep only when a signal interrupts it, Modules/timemodule.c:2285-2293; os.write,
# os.read and os.waitpid likewise, in posixmodule.c's EINTR loops; os.system not at all). So the handler finds the call's
# work done, and the call's work stays done when the handler raises. Design point 5 as worded puts a look before every
# blocking primitive waits, in both fidelities (core's interruptible() and p_system have it); a build with that look runs
# these handlers before the calls, and fails this test with the literal expectations.md gives for it. The reviews proposed
# that look for lean builds only; the lead decides, and if it stays in exact builds this becomes a pinned deviation.
OWED = r"""
import os
import signal
import time

INT, U1 = signal.SIGINT, signal.SIGUSR1
log = []


class Stop(Exception):
    pass


def owed():
    signal.pthread_sigmask(signal.SIG_BLOCK, [INT, U1])
    signal.raise_signal(U1)
    signal.raise_signal(INT)
    try:
        signal.pthread_sigmask(signal.SIG_UNBLOCK, [INT, U1])
    except KeyboardInterrupt:
        pass


def stops(signum, frame):
    raise Stop(signum)


def main():
    global log
    signal.signal(INT, signal.default_int_handler)
    fd = os.open("written", os.O_RDWR | os.O_CREAT | os.O_TRUNC, 0o600)
    r, w = os.pipe()
    child = os.posix_spawn("/bin/sh", ["sh", "-c", "exit 3"], {})

    # a handler that returns: what it finds done
    signal.signal(U1, lambda signum, frame: log.append(("the handler finds the file at", os.lseek(fd, 0, os.SEEK_CUR))))
    owed()
    os.write(fd, b"abc")
    log += ["os.write returned"]
    signal.signal(U1, lambda signum, frame: log.append(("the handler finds the command run", os.path.exists("ran"))))
    owed()
    os.system(": > ran")
    log += ["os.system returned"]

    # a handler that raises: the call's work is done all the same
    signal.signal(U1, stops)
    owed()
    try:
        os.write(fd, b"def")
        log += ["not reached"]
    except Stop:
        log += ["Stop came out of os.write"]
    os.write(w, b"xy")
    owed()
    try:
        os.read(r, 1)
        log += ["not reached"]
    except Stop:
        log += ["Stop came out of os.read"]
    started = time.monotonic()
    owed()
    try:
        time.sleep(0.2)
        log += ["not reached"]
    except Stop:
        log += [("Stop came out of time.sleep, which had slept", time.monotonic() - started >= 0.2)]
    owed()
    try:
        os.waitpid(child, 0)
        log += ["not reached"]
    except Stop:
        log += ["Stop came out of os.waitpid"]
    signal.signal(U1, signal.SIG_DFL)
    try:
        os.waitpid(child, os.WNOHANG)
        reaped = False
    except ChildProcessError:
        reaped = True
    size = os.lseek(fd, 0, os.SEEK_END)
    os.close(fd)
    print(log)
    print("octets in the file:", size, "| left in the pipe:", os.read(r, 10), "| the child was reaped:", reaped)
    os.unlink("written")
    os.unlink("ran")


main()
"""

OWED_SAID = (
    "[('the handler finds the file at', 3), 'os.write returned', ('the handler finds the command run', True), 'os.system returned', "
    "'Stop came out of os.write', 'Stop came out of os.read', ('Stop came out of time.sleep, which had slept', True), 'Stop came out of os.waitpid']\n"
    "octets in the file: 6 | left in the pipe: b'y' | the child was reaped: True\n")


def test_a_handler_owed_when_a_call_waits_runs_when_the_call_is_over() -> None:
    """The handler finds the write made, the command run; raising, it leaves the octets written, the byte read, the sleep
    slept and the child reaped (see OWED's comment: this fails while the runtime looks before a call waits)."""
    if shutil.which("g++") is None:
        return
    with tempfile.TemporaryDirectory() as tmp:
        cpython, compiled = _two(OWED, tmp)
        ref = _run(cpython, tmp)
        got = _run(compiled, tmp)
    assert ref == (OWED_SAID, "", 0), ref
    assert got == ref, got


# ---------------------------------------------------------------------------------------------------------------------------
# rows of other test files that this increment changes (expectations.md lists them with their lines); what they become
# ---------------------------------------------------------------------------------------------------------------------------

# test_posix.py test_what_the_runtime_has_not_stops_by_name loses ("os.kill(0, 0)", ...) and ("os.killpg(0, 0)", ...): both
# calls succeed now. In their place, here in test_signals.py (nothing is added to test_posix.py): the words of os.kill and
# os.killpg, and when the handler has run.
KILL = r"""
import os
import signal


def m(g):
    try:
        return repr(g())
    except BaseException as e:
        return type(e).__name__ + ": " + str(e)


class Stop(Exception):
    pass


def stop(signum, frame):
    raise Stop(signum)


me, nobody = os.getpid(), 2**22 + 1       # no process has a number above the system's largest
got = []
print("kill:", m(lambda: os.kill(me, 0)), m(lambda: os.kill(nobody, 0)), m(lambda: os.kill(me, 65)), m(lambda: os.kill(me, -1)), m(lambda: os.kill(me, 2**40)),
      m(lambda: os.kill(2**31, 0)), m(lambda: os.kill(-2**31 - 1, 0)), m(lambda: os.kill(me, 2**70)), m(lambda: os.kill("a", 0)), m(lambda: os.kill(me, "a")),
      m(lambda: os.kill(1.5, 0)), m(lambda: os.kill(me, 1.5)), m(lambda: os.kill(me)), m(lambda: os.kill(me, 0, 1)), m(lambda: os.kill(pid=me, signal=0)), sep="\n  ")
print("killpg:", m(lambda: os.killpg(os.getpgrp(), 0)), m(lambda: os.killpg(0, 0)), m(lambda: os.killpg(nobody, 0)), m(lambda: os.killpg(os.getpgrp(), 65)),
      m(lambda: os.killpg(os.getpgrp(), -1)), m(lambda: os.killpg(-5, 0)), m(lambda: os.killpg(os.getpgrp(), 2**40)), m(lambda: os.killpg(2**31, 0)),
      m(lambda: os.killpg("a", 0)), m(lambda: os.killpg(me, "a")), m(lambda: os.killpg(me)), m(lambda: os.killpg(me, 0, 1)), m(lambda: os.killpg(pgid=me, signal=0)), sep="\n  ")

# a signal the program sends itself: the handler has run when the call returns, and what it raises comes out of the call
signal.signal(signal.SIGUSR1, lambda signum, frame: got.append((signum, type(frame).__name__)))
print("to itself:", [os.kill(me, signal.SIGUSR1), list(got)], [os.kill(me, signal.Signals.SIGUSR1), len(got)])
signal.signal(signal.SIGUSR2, signal.SIG_IGN)
print("ignored, and what the system ignores:", os.kill(me, signal.SIGUSR2), os.kill(me, signal.SIGCHLD), os.kill(me, signal.SIGURG), os.kill(me, signal.SIGWINCH), len(got))
signal.signal(signal.SIGUSR1, stop)
print("a handler that raises:", m(lambda: os.kill(me, signal.SIGUSR1)))

# a signal for the program's own group reaches whoever else is in it: only as the group's leader, alone in it
if os.getpgrp() != me:
    print("the program does not lead its group: nothing is sent to the group")
else:
    got.clear()
    signal.signal(signal.SIGUSR1, lambda signum, frame: got.append((signum, type(frame).__name__)))
    print("to its group:", [os.killpg(me, signal.SIGUSR1), list(got)], [os.killpg(0, signal.SIGUSR1), len(got)], [os.kill(0, signal.SIGUSR1), len(got)],
          [os.kill(-me, signal.SIGUSR1), len(got)])
    signal.signal(signal.SIGUSR1, stop)
    print("a handler that raises:", m(lambda: os.killpg(me, signal.SIGUSR1)), m(lambda: os.kill(0, signal.SIGUSR1)))
"""

KILLED = (
    "kill:\n  None\n  ProcessLookupError: [Errno 3] No such process\n  OSError: [Errno 22] Invalid argument\n  OSError: [Errno 22] Invalid argument\n  None\n"
    "  OverflowError: Python int too large to convert to C int\n  OverflowError: Python int too large to convert to C int\n"
    "  OverflowError: Python int too large to convert to C ssize_t\n  TypeError: 'str' object cannot be interpreted as an integer\n"
    "  TypeError: 'str' object cannot be interpreted as an integer\n  TypeError: 'float' object cannot be interpreted as an integer\n"
    "  TypeError: 'float' object cannot be interpreted as an integer\n  TypeError: kill expected 2 arguments, got 1\n  TypeError: kill expected 2 arguments, got 3\n"
    "  TypeError: posix.kill() takes no keyword arguments\n"
    "killpg:\n  None\n  None\n  ProcessLookupError: [Errno 3] No such process\n  OSError: [Errno 22] Invalid argument\n  OSError: [Errno 22] Invalid argument\n"
    "  OSError: [Errno 22] Invalid argument\n  OverflowError: Python int too large to convert to C int\n  OverflowError: Python int too large to convert to C int\n"
    "  TypeError: 'str' object cannot be interpreted as an integer\n  TypeError: 'str' object cannot be interpreted as an integer\n"
    "  TypeError: killpg expected 2 arguments, got 1\n  TypeError: killpg expected 2 arguments, got 3\n  TypeError: posix.killpg() takes no keyword arguments\n"
    "to itself: [None, [(10, 'frame')]] [None, 2]\nignored, and what the system ignores: None None None None 2\na handler that raises: Stop: 10\n"
    "to its group: [None, [(10, 'frame')]] [None, 2] [None, 3] [None, 4]\na handler that raises: Stop: 10 Stop: 10\n")


def test_kill_and_killpg() -> None:
    """os.kill looks for the signal itself once the system has taken it (os_kill_impl: PyErr_CheckSignals); os.killpg has no
    look of its own, and CPython's handler runs at the look after the call, which the runtime gives the function's end. Run
    in a session of its own: the program sends real signals to its group only as that group's leader."""
    if shutil.which("g++") is None:
        return
    with tempfile.TemporaryDirectory() as tmp:
        cpython, compiled = _two(KILL, tmp)
        ref = _run(cpython, tmp, session=True)
        got = _run(compiled, tmp, session=True)
    assert ref == (KILLED, "", 0), ref
    assert got == ref, got


# test_thread.py REFUSED loses ("import _thread\n_thread.interrupt_main()\n", "interrupt_main"). In its place, here in
# test_signals.py (nothing is added to test_thread.py): the program below, compared with CPython by _same, and one test of
# the uncaught way out.
INTERRUPT_MAIN = r"""
import _thread
import signal
import sys

log = []


def m(g):
    try:
        return repr(g())
    except BaseException as e:
        return type(e).__name__ + ": " + str(e)


def note(signum, frame):
    log.append((signum, type(frame).__name__))


def unraisable(u):
    log.append((u.err_msg, type(u.exc_value).__name__, str(u.exc_value), u.object))


sys.unraisablehook = unraisable
signal.signal(signal.SIGUSR1, note)
print("SIGINT, the default:", m(lambda: _thread.interrupt_main()), m(lambda: _thread.interrupt_main(2)), m(lambda: _thread.interrupt_main(signal.SIGINT)))
done = _thread.interrupt_main(signal.SIGUSR1)
log.append("the next statement")
print("a signal with a handler:", done, log)
log.clear()
signal.signal(signal.SIGUSR2, signal.SIG_IGN)
print("at its default, ignored, never to be handled:", _thread.interrupt_main(signal.SIGTERM), _thread.interrupt_main(signal.SIGUSR2), _thread.interrupt_main(signal.SIGPIPE),
      _thread.interrupt_main(signal.SIGKILL), log)
done = _thread.interrupt_main(32)
log.append("the next statement")
print("a number the table has nothing for:", done, log)
log.clear()
# nothing is sent: the mask is not asked, nothing is pending afterwards
signal.pthread_sigmask(signal.SIG_BLOCK, [signal.SIGUSR1])
_thread.interrupt_main(signal.SIGUSR1)
print("blocked:", log, sorted(signal.sigpending()))
signal.pthread_sigmask(signal.SIG_UNBLOCK, [signal.SIGUSR1])
log.clear()


class Stop(Exception):
    pass


def stop(signum, frame):
    raise Stop(signum)


signal.signal(signal.SIGUSR1, stop)
print("a handler that raises:", m(lambda: _thread.interrupt_main(signal.SIGUSR1)))

# left waiting behind a Python handler that raised (the evaluation loop's note is down): the look at the end of
# interrupt_main of a signal at its default finds nothing, since it trips nothing; of a signal with a handler, it runs
# both, in the signals' order
signal.signal(signal.SIGHUP, stop)
signal.signal(signal.SIGUSR1, note)
signal.signal(signal.SIGUSR2, note)
signal.pthread_sigmask(signal.SIG_BLOCK, [signal.SIGHUP, signal.SIGUSR1])
signal.raise_signal(signal.SIGUSR1)
signal.raise_signal(signal.SIGHUP)
try:
    signal.pthread_sigmask(signal.SIG_UNBLOCK, [signal.SIGHUP, signal.SIGUSR1])
except Stop:
    pass
_thread.interrupt_main(signal.SIGTERM)
log.append("after interrupt_main of a signal at its default")
_thread.interrupt_main(signal.SIGUSR2)
log.append("after interrupt_main of a signal with a handler")
print("left waiting:", log)
if len(sys.argv) > 1:
    print("before", flush=True)
    _thread.interrupt_main()
    print("not reached")
"""


def test_interrupt_main_trips_the_signal_without_sending_it() -> None:
    """_thread.interrupt_main is PyErr_SetInterruptEx: the whole of trip_signal for a signal that has a handler, nothing for
    one at its default or ignored, the report of the look for a number the table holds None for; the handler has run when
    the next statement runs (CPython's look after the call)."""
    _same(INTERRUPT_MAIN)


def test_interrupt_main_uncaught_ends_the_process_by_sigint() -> None:
    """SIGINT tripped by interrupt_main, whose look at its end raises the KeyboardInterrupt nobody catches."""
    if shutil.which("g++") is None:
        return
    with tempfile.TemporaryDirectory() as tmp:
        cpython, compiled = _two(INTERRUPT_MAIN, tmp)
        ref = _run([*cpython, "uncaught"], tmp)
        got = _run([*compiled, "uncaught"], tmp)
    assert (ref[0].splitlines()[-1], ref[1], ref[2]) == ("before", 'Traceback (most recent call last):\n  File "prog.py", line 77, in <module>\nKeyboardInterrupt\n', -2), ref
    assert got == ref, got


# A timed wait on a lock nobody else can release looks for signals now (CPython: Py_MakePendingCalls in the lock's wait), so
# a handler can end it. No row of test_thread.py changes for it (test_a_timed_wait_takes_its_time stays: no signal, False);
# this is new. The timer is 0.05 s ahead and the waits 30 s long; nothing the timer's rows print depends on when it fires (a
# handler that ran before the wait began gives the same lines). The row "a handler owed when the wait begins" has no timer:
# its handler is owed on purpose, and the row shows that the wait does not look before it waits (expectations.md, the
# section on the look before a call).
LOCK_WAITS_TIMED = r"""
import _thread
import signal
import threading
import time

SOON = 0.05
count = []
lock = _thread.lock()
lock.acquire()


class Stop(Exception):
    pass


def release(signum, frame):
    count.append(type(frame).__name__)
    lock.release()


def stop(signum, frame):
    raise Stop(signum)


def note(signum, frame):
    count.append(signum)


# a handler that releases the lock ends the wait at once, long before its time is up
signal.signal(signal.SIGALRM, release)
started = time.monotonic()
signal.setitimer(signal.ITIMER_REAL, SOON)
print("released by a handler:", lock.acquire(True, 30), count, time.monotonic() - started < 10, lock.locked())

# what a handler raises comes out of the wait, and the lock is as it was
signal.signal(signal.SIGALRM, stop)
started = time.monotonic()
signal.setitimer(signal.ITIMER_REAL, SOON)
try:
    print(lock.acquire(True, 30))
except Stop as e:
    print("left by a handler's exception:", e.args, time.monotonic() - started < 10, lock.locked())

# a handler that returns leaves the wait waiting, to its first deadline
count.clear()
signal.signal(signal.SIGALRM, note)
started = time.monotonic()
signal.setitimer(signal.ITIMER_REAL, SOON)
print("a handler that returns:", lock.acquire(True, 0.3), count, 0.3 <= time.monotonic() - started < 10)

# a handler owed when the wait begins (SIGINT's default_int_handler raised in the call that unblocked both, and its note is
# still up): the wait does not look before it begins (the lock's wait handles signals only when one interrupts it,
# Include/internal/pycore_lock.h:43-44), so it times out, and the handler that releases the lock runs at the look after
# the call
count.clear()
signal.signal(signal.SIGINT, signal.default_int_handler)
signal.signal(signal.SIGUSR1, release)
signal.pthread_sigmask(signal.SIG_BLOCK, [signal.SIGINT, signal.SIGUSR1])
signal.raise_signal(signal.SIGUSR1)
signal.raise_signal(signal.SIGINT)
try:
    signal.pthread_sigmask(signal.SIG_UNBLOCK, [signal.SIGINT, signal.SIGUSR1])
except KeyboardInterrupt:
    pass
print("a handler owed when the wait begins:", lock.acquire(True, 0.3), count, lock.locked())
signal.signal(signal.SIGUSR1, signal.SIG_DFL)

# the same through threading: an RLock held by a handle's join, a Condition's and an Event's timed wait
event = threading.Event()
signal.signal(signal.SIGALRM, lambda signum, frame: event.set())
started = time.monotonic()
signal.setitimer(signal.ITIMER_REAL, SOON)
print("an Event set by a handler:", event.wait(30), time.monotonic() - started < 10)
with_lock = threading.Lock()
with_lock.acquire()
signal.signal(signal.SIGALRM, lambda signum, frame: with_lock.release())
signal.setitimer(signal.ITIMER_REAL, SOON)
print("threading.Lock:", with_lock.acquire(timeout=30))
print(signal.getitimer(signal.ITIMER_REAL))
"""

# An untimed wait on a lock the only thread holds is a real wait (docs/DECISIONS.md, the _signal increment): the decision of
# 2026-11-05 stopped it by name "since hanging would be right only with signals, which are not there yet". Such a program now
# waits for ever, as it does under CPython, until a handler frees the lock or raises; this takes the place of the rows that
# stopped (test_thread.py REFUSED, test_system_modules.py test_what_is_absent_stops_by_name).
LOCK_WAITS_UNTIMED = r"""
import _thread
import signal
import threading

SOON = 0.05
lock = _thread.lock()
lock.acquire()


class Stop(Exception):
    pass


def stop(signum, frame):
    raise Stop(signum)


signal.signal(signal.SIGALRM, lambda signum, frame: lock.release())
signal.setitimer(signal.ITIMER_REAL, SOON)
print("released by a handler:", lock.acquire(), lock.locked())
signal.signal(signal.SIGALRM, stop)
signal.setitimer(signal.ITIMER_REAL, SOON)
try:
    print(lock.acquire())
except Stop as e:
    print("left by a handler's exception:", e.args, lock.locked())
signal.setitimer(signal.ITIMER_REAL, SOON)
try:
    with lock:
        print("not reached")
except Stop as e:
    print("a with statement:", e.args, lock.locked())
event = threading.Event()
signal.signal(signal.SIGALRM, lambda signum, frame: event.set())
signal.setitimer(signal.ITIMER_REAL, SOON)
print("an Event set by a handler:", event.wait())
held = threading.Lock()
held.acquire()
signal.signal(signal.SIGALRM, lambda signum, frame: held.release())
signal.setitimer(signal.ITIMER_REAL, SOON)
print("threading.Lock:", held.acquire())
print(signal.getitimer(signal.ITIMER_REAL))
"""


# The five programs of those rows, each saying "ready" before the wait that nothing but a signal can end: under CPython all
# five wait, and SIGINT's KeyboardInterrupt comes out of the wait.
STILL_WAITING = {
    "a lock taken twice": "import _thread\nl = _thread.lock()\nl.acquire()\nprint('ready', flush=True)\nl.acquire()\n",
    "with, twice": "import _thread\nl = _thread.lock()\nprint('ready', flush=True)\nwith l:\n    with l:\n        pass\n",
    "an RLock another thread owns": "import _thread\nr = _thread.RLock()\nr._acquire_restore((1, 5))\nprint('ready', flush=True)\nr.acquire()\n",
    "joining a thread that is not there": "import _thread\nh = _thread._make_thread_handle(5)\nprint('ready', flush=True)\nh.join()\n",
    "threading.Lock taken twice": "import threading\nlk = threading.Lock()\nlk.acquire()\nprint('ready', flush=True)\nlk.acquire()\n",
}


def test_a_handler_ends_a_timed_wait_on_a_lock() -> None:
    _same(LOCK_WAITS_TIMED)


def test_a_handler_ends_an_untimed_wait_on_a_lock() -> None:
    _same(LOCK_WAITS_UNTIMED)


def _interrupted_while_waiting(command: list[str], tmp: str) -> tuple[str, str, int]:
    with _Running(command, tmp) as running:
        assert running.line() == "ready\n", running.said
        running.asleep()
        running.send(signal.SIGINT)
        out, err, status = running.end()
    return out, mask_stderr(err), status


def test_a_wait_nobody_can_end_waits_for_a_signal() -> None:
    """What the five stops "no other thread can release" become if the untimed wait is a real one: the program waits, as
    under CPython, and Ctrl-C ends the wait with a KeyboardInterrupt at its line."""
    if shutil.which("g++") is None:
        return
    for name, text in STILL_WAITING.items():
        with tempfile.TemporaryDirectory() as tmp:
            cpython, compiled = _two(text, tmp)
            ref = _interrupted_while_waiting(cpython, tmp)
            got = _interrupted_while_waiting(compiled, tmp)
        line = 4 if name == "joining a thread that is not there" else 5
        assert ref == ("ready\n", f'Traceback (most recent call last):\n  File "prog.py", line {line}, in <module>\nKeyboardInterrupt\n', -2), (name, ref)
        assert got == ref, (name, got)


# ===========================================================================================================================
# THE LEAN BUILD'S TESTS: build(..., fidelity="lean"), deviation D-24
# ===========================================================================================================================
# A lean build has no look in generated code (no BELLA_LOOK at a function's entry or a loop's turn), does not install
# default_int_handler at start (SIGINT stays as the program found it), and gives a handler None for its frame; every look
# that lives in the runtime library stays. The first three tests pin what differs from CPython the way test_instance_dict.py
# pins D-23: CPython's answer and the lean build's are each asserted against its own literal, so a test fails when the two
# come to agree. CPython's literals were measured on 3.15.2, the lean build's on its first run (2026-11-11). The last
# test is no deviation: where only the runtime's own looks matter a lean build must still say what CPython says.

Row = tuple[str, object, object, object, object]     # a name, CPython's outcome and its literal, the lean build's and its literal


def _pinned(rows: Sequence[Row]) -> None:
    for name, ref, of_cpython, _got, _of_lean in rows:
        assert ref == of_cpython, ("CPython", name, ref)
    for name, _ref, of_cpython, got, of_lean in rows:
        assert got == of_lean, ("lean", name, got)
        assert of_lean != of_cpython, ("D-24 is over for this row: remove it from the register and the specification", name)


TRACEBACK = ("Traceback (most recent call last):", "KeyboardInterrupt")


def test_d24_lean_sigint_ends_the_program_by_the_signal() -> None:
    """Deviation D-24. A lean build leaves SIGINT as it found it, so Ctrl-C ends the program as it ends any program without
    a handler: no KeyboardInterrupt, no traceback, no exit hook, stdout's buffer lost; a parent sees -2 either way. So in a
    loop, in a recursion, between naps, in a sleep, in a read, and when the program raises SIGINT at itself. getsignal says
    SIG_DFL where CPython says default_int_handler."""
    if shutil.which("g++") is None:
        return
    rows: list[Row] = []
    with tempfile.TemporaryDirectory() as tmp:
        cpython, lean = _two(WAITING, tmp, "lean")
        for way in ("loop", "recursion", "naps", "sleep", "read"):
            rows.append((way, _with_the_default_handler(cpython, way, tmp)[:3], ("SIGINT: default_int_handler\nready\n", TRACEBACK, -2),
                         _with_the_default_handler(lean, way, tmp)[:3], ("SIGINT: SIG_DFL\nready\n", ("", ""), -2)))
        ref, got = _run([*cpython, "itself", "default"], tmp), _run([*lean, "itself", "default"], tmp)
        rows.append(("itself", (ref[0], _ends(ref[1]), ref[2]), ("SIGINT: default_int_handler\nready\n", TRACEBACK, -2),
                     (got[0], _ends(got[1]), got[2]), ("SIGINT: SIG_DFL\nready\n", ("", ""), -2)))
    with tempfile.TemporaryDirectory() as tmp:
        cpython, lean = _two(ENDING, tmp, "lean")
        rows.append(("what the buffer held", _ended_by(cpython, signal.SIGINT, tmp),
                     ("written, and still in the buffer\nan exit hook ran\na module's object is released\n", TRACEBACK, -2),
                     _ended_by(lean, signal.SIGINT, tmp), ("", ("", ""), -2)))
    _pinned(rows)


# A timer fires 0.05 s into half a second of computing (a loop that asks the clock: no look in a lean build), then the
# program sleeps, then raises the signal at itself.
LEAN_ORDER = r"""
import signal
import time

log = []


def note(signum, frame):
    log.append("the handler, given " + type(frame).__name__)


def compute(seconds):
    until = time.monotonic() + seconds
    turns = 0
    while time.monotonic() < until:
        turns += 1
    return turns


signal.signal(signal.SIGALRM, note)
signal.setitimer(signal.ITIMER_REAL, 0.05)
compute(0.5)
log.append("computed")
time.sleep(0.01)
log.append("slept")
signal.raise_signal(signal.SIGALRM)
log.append("raised")
print(log)
"""


def test_d24_lean_a_handler_runs_at_the_runtimes_next_look_and_is_given_none() -> None:
    """Deviation D-24. With no look in generated code a Python handler waits for the next look of the runtime: the next
    sleep (before it blocks if a lean build looks there, when a signal interrupts it, when it returns), the next read, a
    signal the program raises at itself, os.kill and os.killpg. There it is given None where CPython gives the frame. (A
    loop or a recursion that never reaches the runtime is not ended by a handler in a lean build; nothing here waits for
    that.)"""
    if shutil.which("g++") is None:
        return
    rows: list[Row] = []
    with tempfile.TemporaryDirectory() as tmp:
        cpython, lean = _two(WAITING, tmp, "lean")
        for way in ("naps", "sleep", "read"):
            of_cpython = WITH_A_PYTHON_HANDLER[way]
            of_lean = (of_cpython[0].replace("default_int_handler", "SIG_DFL").replace("handler 10 frame", "handler 10 NoneType"), "", 0)
            rows.append((way, _with_a_python_handler(cpython, way, tmp), of_cpython, _with_a_python_handler(lean, way, tmp), of_lean))
    with tempfile.TemporaryDirectory() as tmp:
        cpython, lean = _two(LEAN_ORDER, tmp, "lean")
        rows.append(("the order", _run(cpython, tmp), ("['the handler, given frame', 'computed', 'slept', 'the handler, given frame', 'raised']\n", "", 0),
                     _run(lean, tmp), ("['computed', 'the handler, given NoneType', 'slept', 'the handler, given NoneType', 'raised']\n", "", 0)))
    with tempfile.TemporaryDirectory() as tmp:
        cpython, lean = _two(KILL, tmp, "lean")
        rows.append(("os.kill and os.killpg", _run(cpython, tmp, session=True), (KILLED, "", 0),
                     _run(lean, tmp, session=True), (KILLED.replace("(10, 'frame')", "(10, 'NoneType')"), "", 0)))
    _pinned(rows)


def test_d24_lean_tables() -> None:
    """Deviation D-24, seen in the tables: SIGINT reads SIG_DFL in a lean program and in the lean program it starts, and the
    slot the exit empties held 0, not default_int_handler. Everything else of those two tests is as under CPython."""
    if shutil.which("g++") is None:
        return
    rows: list[Row] = []
    with tempfile.TemporaryDirectory() as tmp:
        cpython, lean = _two(INHERITS, tmp, "lean")
        of_lean = (INHERITED[0].replace("SIGINT=default_int_handler", "SIGINT=SIG_DFL"), "", 0)
        rows.append(("inherits", _run([*cpython, "parent", *cpython, "child"], tmp), INHERITED, _run([*lean, "parent", *lean, "child"], tmp), of_lean))
    with tempfile.TemporaryDirectory() as tmp:
        cpython, lean = _two(HANDLERS_AT_EXIT, tmp, "lean")
        said = ("the program ends\nan exit hook; getsignal: [{}, 'Handler', 1, 0]\nthe handler object is released; getsignal: [None, None, 1, 0]\n"
                "a module's object is released; getsignal: [None, None, None, None]\n")
        rows.append(("at exit", _run([*cpython, "ends"], tmp), (said.format("'builtin_function_or_method'"), "", 0), _run([*lean, "ends"], tmp), (said.format(0), "", 0)))
    _pinned(rows)


def test_lean_keeps_every_look_of_the_runtime() -> None:
    """No deviation: what does not depend on a look of generated code, or on who installed SIGINT's handler, is the same in
    a lean build. An uncaught KeyboardInterrupt still ends the process by SIGINT; a program that gives SIGINT
    default_int_handler itself gets its KeyboardInterrupt at the next sleep or read; the look after the main module; the
    looks at the end of os.system, os.waitpid and os.wait (NEXT_LOOKS's children, whose handler notes numbers only); a
    signal nobody handles. (KILL is pinned above; INTERRUPT_MAIN and LOCK_WAITS_TIMED print what a handler is given and
    REFUSALS whether SIGINT has default_int_handler, so a lean build differs on them by D-24 alone; they are not here.
    LATE's buffered rows are not here either: whether a lean build's write looks before it writes, which would run the
    handler before the buffered text goes out, is the lead's to rule; the rows with nothing buffered hold either way.)"""
    if shutil.which("g++") is None:
        return
    with tempfile.TemporaryDirectory() as tmp:
        cpython, lean = _two(WAITING, tmp, "lean")
        for way in ("naps", "sleep", "read"):
            waited = _with_the_default_handler(cpython, way, tmp, "installed")
            waited_lean = _with_the_default_handler(lean, way, tmp, "installed")
            assert waited[:3] == ("SIGINT: default_int_handler\nready\n", TRACEBACK, -2), (way, waited)
            assert waited_lean == waited, (way, waited_lean)
    with tempfile.TemporaryDirectory() as tmp:
        cpython, lean = _two(UNCAUGHT, tmp, "lean")
        for way in ("bare", "with arguments", "a subclass", "the hook replaced", "SIGINT ignored by the program", "SIGINT handled by the program", "SIGINT blocked",
                    "SystemExit while it is handled"):
            ran = _run([*cpython, way], tmp)
            ran_lean = _run([*lean, way], tmp)
            assert ran == UNCAUGHT_WAYS[way], (way, ran)
            assert ran_lean == ran, (way, ran_lean)
    with tempfile.TemporaryDirectory() as tmp:
        cpython, lean = _two(LATE, tmp, "lean")
        for (way, buffer, ending), expected in LATE_WAYS.items():
            if buffer == "empty":
                ran = _run([*cpython, way, buffer, ending], tmp)
                ran_lean = _run([*lean, way, buffer, ending], tmp)
                assert ran == expected, (way, buffer, ending, ran)
                assert ran_lean == ran, (way, buffer, ending, ran_lean)
    with tempfile.TemporaryDirectory() as tmp:
        cpython, lean = _two(NEXT_LOOKS, tmp, "lean")
        ran = _run([*cpython, "children"], tmp)
        ran_lean = _run([*lean, "children"], tmp)
        assert ran == (CHILDREN, "", 0), ran
        assert ran_lean == ran, ran_lean
    with tempfile.TemporaryDirectory() as tmp:
        cpython, lean = _two(ENDING, tmp, "lean")
        ended = _ended_by(cpython, signal.SIGTERM, tmp)
        ended_lean = _ended_by(lean, signal.SIGTERM, tmp)
        assert ended == ("", ("", ""), -15), ended
        assert ended_lean == ended, ended_lean


if __name__ == "__main__":
    for name, test in list(globals().items()):
        if name.startswith("test_"):
            test()
