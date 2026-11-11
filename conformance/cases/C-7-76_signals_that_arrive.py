# clause: C-7-76
# spec: section 7
# status: P1
# source: dialect specification sections 3 and 7 (process and signals), Python/bytecodes.c (RESUME and JUMP_BACKWARD: _CHECK_PERIODIC_IF_NOT_YIELD_FROM, _CHECK_PERIODIC), Python/ceval_gil.c (_Py_HandlePending, handle_signals), Modules/signalmodule.c (signal_handler, trip_signal, _PyErr_CheckSignalsTstate, signal_pause_impl, signal_setitimer_impl, signal_siginterrupt_impl, signal_sigtimedwait_impl), Modules/timemodule.c (pysleep), Modules/posixmodule.c (os_read_impl), Python/fileutils.c (_Py_read), Python/pylifecycle.c (PyOS_setsig), Modules/_threadmodule.c (_thread_lock_acquire_impl), Python/lock.c (_PyMutex_LockTimed)
"""Signals that arrive by themselves, from a timer. First while the program computes: nobody asks, so the program's own
code has to look. It looks at every turn of a loop and wherever a function or a generator starts or a generator goes on
after a yield, so a handler ends a loop that does nothing else, a recursion that would not return and a generator that is
driven on; and a handler that raises does so after a loop's body (after the finally body a continue runs through) and before
a function's own try, and inside a generator's try around its yields. Then while the program waits in the system (sleep,
pause, a read of an empty pipe, a wait for another signal, a wait for a lock): the handler runs there, and the wait goes on
or the handler's exception comes out of it. A wait with a time of its own keeps its first deadline however often a handler
interrupts it. After siginterrupt(False) a sleep, a pause and a wait for a lock with a timeout are still left for the
handler: the system starts none of them again by itself."""
# ruff: noqa: E501
# A clock is involved, so nothing is printed that depends on when the signal came: only who ran, in which order, and what
# came of it. A handler that ran earlier than it was meant to (the process was held up) leaves the same lines, and so does a
# signal that came after the program's last look and before the system call began: the call then ends by its own time, at
# the next arrival of a timer that repeats, or by the signal's byte on the wakeup descriptor, and the handler runs there or as
# the call returns. Nothing waits for ever: a loop that no handler ended gives up after its count, a wait has a time of its
# own (LONG) or a timer that repeats, and a read of a pipe only the handler writes to has a child that writes to it after LONG.
import itertools
import os
import signal
import sys
import threading
import time
import types
from collections.abc import Iterator

ALRM, U1 = signal.SIGALRM, signal.SIGUSR1
SOON = 0.005             # a timer for a program that computes, or that will wait whenever the signal comes
EVERY = 0.02             # and how often a timer that repeats comes again
NAP = 0.3
LONG = 5                 # a wait that only a handler is meant to end early
TURNS = 100_000_000      # far more turns of a loop than fit before the timer: what the loop does if no handler ends it
DEPTH = 26               # the same for calls: a tree of 2**26 of them,
CALLS = 30_000_000       # calls made one after the other, and a generator's turns,
STARTS = 10_000_000      # and generators started,
YIELDERS = 1_000_000     # and generators that yield twenty times

log: list[object] = []
flag = False
first = True
inside = False
phase = 0
count = 0
arrivals = 0
pipe_end = -1
gate = threading.Lock()


def m(f: object, *args: object, **kwargs: object) -> str:
    try:
        return repr(f(*args, **kwargs)) if callable(f) else "not callable"
    except OSError as e:
        return type(e).__name__ + ": " + repr((e.errno, e.strerror, e.filename))
    except Exception as e:
        return type(e).__name__


def taken() -> list[object]:
    """What the handlers and the program wrote down since the last time."""
    seen = list(log)
    log.clear()
    return seen


class Stop(Exception):
    pass


def note(signum: int, frame: types.FrameType | None) -> None:
    log.append(signum)


def sets_flag(signum: int, frame: types.FrameType | None) -> None:
    global flag
    flag = True
    log.append((signum, type(frame).__name__))


def stops(signum: int, frame: types.FrameType | None) -> None:
    log.append(("stops", signum))
    raise Stop(signum)


def once(signum: int, frame: types.FrameType | None) -> None:
    """For a timer that repeats: the first arrival is written down, the others say nothing."""
    global first
    if first:
        first = False
        log.append(("woken by", signum))


def stops_once(signum: int, frame: types.FrameType | None) -> None:
    global first
    if first:
        first = False
        log.append(("stops", signum))
        raise Stop(signum)


def counts(signum: int, frame: types.FrameType | None) -> None:
    """Three arrivals, then the timer is taken away from inside the handler."""
    global count
    if count < 3:
        count += 1
        if count == 3:
            signal.setitimer(signal.ITIMER_REAL, 0)


def arrives(signum: int, frame: types.FrameType | None) -> None:
    """For a timer that repeats: each arrival is counted, and after LONG the timer is taken away from inside the handler."""
    global arrivals
    arrivals += 1
    if arrivals >= LONG / EVERY:
        signal.setitimer(signal.ITIMER_REAL, 0)


def raises_inside(signum: int, frame: types.FrameType | None) -> None:
    """For a timer that repeats: it raises only while a generator is between its first yield and its last."""
    if inside:
        raise Stop(signum)


def sees_phase(signum: int, frame: types.FrameType | None) -> None:
    global flag
    if not flag:
        flag = True
        log.append(("the phase the handler saw", phase))


def writes_once(signum: int, frame: types.FrameType | None) -> None:
    """For a timer that repeats: the first arrival writes a byte to the pipe that is read, the others say nothing."""
    global first
    if first:
        first = False
        log.append("handler")
        os.write(pipe_end, b"P")


def sends(signum: int, frame: types.FrameType | None) -> None:
    global first
    if first:
        first = False
        log.append("the alarm's handler")
        signal.raise_signal(U1)


def releases(signum: int, frame: types.FrameType | None) -> None:
    global first
    if first:
        first = False
        log.append("the alarm's handler")
        gate.release()


def quiet() -> None:
    """The timer is taken away and SIGALRM ignored until the next handler is set. A handler that is still owed a run gets it
    here, and says nothing; one that raises here never ran where it was meant to."""
    try:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(ALRM, signal.SIG_IGN)
    except Stop:
        log.append("a handler ran late")
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(ALRM, signal.SIG_IGN)


def spin() -> str:
    turns = 0
    while not flag and turns < TURNS:
        turns += 1
    return "ended by the handler" if flag else "gave up"


def spin_for() -> str:
    for _ in range(TURNS):
        if flag:
            return "ended by the handler"
    return "gave up"


def spin_continue() -> str:
    turns = 0
    while turns < TURNS:
        turns += 1
        if not flag:
            continue
        return "ended by the handler"
    return "gave up"


def walk(depth: int) -> int:
    """A tree of calls with no loop in it: 2**depth of them reach the bottom, unless the flag cuts the tree short."""
    if flag or depth == 0:
        return 1
    return walk(depth - 1) + walk(depth - 1)


def starts(_: int) -> Iterator[bool]:
    """A generator that ends at once unless the flag is up: where it starts is the only place it can look."""
    if flag:
        yield True


def ticks(turns: int) -> Iterator[bool]:
    """A generator that hands out the flag, turn after turn."""
    for _ in range(turns):
        yield flag


def out_of_a_loop() -> str:
    turns = 0
    try:
        signal.setitimer(signal.ITIMER_REAL, SOON)
        while turns < TURNS:
            turns += 1
    except Stop:
        return "into the except clause around the loop"
    return "gave up"


def out_of_a_comprehension() -> str:
    try:
        signal.setitimer(signal.ITIMER_REAL, SOON)
        kept = [turn for turn in range(TURNS) if flag]
    except Stop:
        return "into the except clause around the comprehension"
    return "gave up" if not kept else "the flag was up"


def turn_and_try() -> str:
    """The look at a loop's turn comes after the body: a try that is all inside the body does not see what it raises."""
    turns = 0
    try:
        signal.setitimer(signal.ITIMER_REAL, SOON)
        while turns < TURNS:
            try:
                turns += 1
            except Stop:
                return "inside the body's try"
    except Stop:
        return "after the body, outside its try"
    return "gave up"


def continue_and_try() -> str:
    """The same when the body goes round by continue, from inside its try."""
    turns = 0
    try:
        signal.setitimer(signal.ITIMER_REAL, SOON)
        while turns < TURNS:
            try:
                turns += 1
                continue
            except Stop:
                return "inside the body's try"
    except Stop:
        return "after the body, outside its try"
    return "gave up"


def continue_and_finally() -> str:
    """continue inside a try with a finally: the turn's look comes after the finally body has run."""
    global phase
    turns = 0
    phase = 2
    signal.setitimer(signal.ITIMER_REAL, SOON)
    while not flag and turns < TURNS:
        try:
            phase = 1
            turns += 1
            continue
        finally:
            phase = 2
    return "ended by the handler" if flag else "gave up"


def continue_out_of_finally() -> list[str]:
    """The same with a handler that raises: the exception comes out after the finally body, which never sees it."""
    turns = 0
    seen: list[str] = []
    try:
        signal.setitimer(signal.ITIMER_REAL, SOON)
        while turns < TURNS:
            try:
                turns += 1
                continue
            finally:
                if sys.exception() is not None:
                    seen.append("the finally body saw the exception")
        seen.append("gave up")
    except Stop:
        seen.append("into the except clause around the loop")
    return seen


def guarded(_: int) -> int:
    """A function that is one try and nothing else."""
    try:
        return 0
    except Stop:
        return 1


def entry_and_try() -> str:
    """The look where a function starts comes before its body: the function's own try does not see what it raises. The
    calls are made by sum and map, so that no loop of the program's looks instead."""
    try:
        signal.setitimer(signal.ITIMER_REAL, SOON)
        inside = sum(map(guarded, range(CALLS)))
    except Stop:
        return "where the function starts, before its own try"
    return "inside the function's own try" if inside else "gave up"


def guarded_start(_: int) -> Iterator[int]:
    try:
        if flag:
            yield 0
    except Stop:
        log.append("inside the generator's own try")


def start_and_try() -> str:
    try:
        signal.setitimer(signal.ITIMER_REAL, SOON)
        sum(itertools.chain.from_iterable(map(guarded_start, range(STARTS))))
    except Stop:
        return "where the generator starts, before its own try"
    return "gave up"


def straight(_: int) -> Iterator[int]:
    """A generator with no loop in it: twenty yields one after the other, all inside its own try. Where it starts the handler
    does not raise; only the looks where it goes on after a yield can find the handler raising."""
    global inside
    try:
        inside = True
        yield 0
        yield 0
        yield 0
        yield 0
        yield 0
        yield 0
        yield 0
        yield 0
        yield 0
        yield 0
        yield 0
        yield 0
        yield 0
        yield 0
        yield 0
        yield 0
        yield 0
        yield 0
        yield 0
        yield 0
        inside = False
    except Stop:
        inside = False
        log.append("caught inside the generator, around its yields")
        yield 1


def after_a_yield() -> str:
    """The generators are driven by any(), which is no code of the program's, and the timer repeats until one of them is found
    between two yields."""
    global inside
    inside = False
    try:
        signal.setitimer(signal.ITIMER_REAL, SOON, EVERY)
        found = any(itertools.chain.from_iterable(map(straight, range(YIELDERS))))
    except Stop:
        inside = False
        return "out of the generator, past its own try"
    return "where it goes on after a yield, inside its own try" if found else "gave up"


def code_looks() -> None:
    global flag
    # a handler that sets a flag ends what does nothing but wait for the flag
    signal.signal(ALRM, sets_flag)
    flag = False
    signal.setitimer(signal.ITIMER_REAL, SOON)
    print("a while loop:", spin(), taken())
    flag = False
    signal.setitimer(signal.ITIMER_REAL, SOON)
    print("a for loop:", spin_for(), taken())
    flag = False
    signal.setitimer(signal.ITIMER_REAL, SOON)
    print("a loop that goes round by continue:", spin_continue(), taken())
    flag = False
    signal.setitimer(signal.ITIMER_REAL, SOON)
    print("a recursion with no loop:", "cut short by the handler" if walk(DEPTH) < 2**DEPTH else "gave up", taken())
    # generators, driven by any(), which is no code of the program's: only the generators themselves can look
    flag = False
    signal.setitimer(signal.ITIMER_REAL, SOON)
    print("generators that start and end:", any(itertools.chain.from_iterable(map(starts, range(STARTS)))), taken())
    flag = False
    signal.setitimer(signal.ITIMER_REAL, SOON)
    print("a generator that is asked again and again:", any(ticks(CALLS)), taken())
    # the timers that count the program's own time
    signal.signal(signal.SIGVTALRM, sets_flag)
    signal.signal(signal.SIGPROF, sets_flag)
    flag = False
    signal.setitimer(signal.ITIMER_VIRTUAL, SOON)
    by_virtual = spin()
    flag = False
    signal.setitimer(signal.ITIMER_PROF, SOON)
    print("the virtual and the profiling timer:", by_virtual, spin(), taken(), signal.setitimer(signal.ITIMER_VIRTUAL, 0), signal.setitimer(signal.ITIMER_PROF, 0))
    quiet()

    # a handler that raises: where the exception appears
    flag = False
    signal.signal(ALRM, stops)
    print("out of a loop:", out_of_a_loop(), taken())
    quiet()
    signal.signal(ALRM, stops)
    print("out of a comprehension:", out_of_a_comprehension(), taken())
    quiet()
    signal.signal(ALRM, stops)
    print("where a loop looks:", turn_and_try(), taken())
    quiet()
    signal.signal(ALRM, stops)
    print("and with continue:", continue_and_try(), taken())
    quiet()
    flag = False
    signal.signal(ALRM, sees_phase)
    ended = continue_and_finally()
    quiet()
    flag = False
    signal.signal(ALRM, stops)
    print("continue inside a try with a finally:", ended, taken(), continue_out_of_finally(), taken())
    quiet()
    signal.signal(ALRM, stops)
    print("where a function looks:", entry_and_try(), taken())
    quiet()
    signal.signal(ALRM, stops)
    print("where a generator looks:", start_and_try(), taken())
    quiet()
    signal.signal(ALRM, raises_inside)
    went_on = after_a_yield()
    quiet()
    print("and where it goes on after a yield:", went_on, taken())


def through_a_read(r: int) -> tuple[bytes, bytes, list[object]]:
    """One read of an empty pipe that nobody writes to but the handler; what it gives, what is left in the pipe after it, and
    who ran. A timer that repeats finds the read waiting (or the program on its way there, and then the read the next time),
    and the handler writes once. A child writes X after LONG, so that a read no handler ends comes to an end all the same."""
    global first
    first = True
    child = os.posix_spawn("/bin/sh", ["sh", "-c", f"sleep {LONG}; printf X"], {"PATH": "/usr/bin:/bin"},
                           file_actions=[(os.POSIX_SPAWN_DUP2, pipe_end, 1), (os.POSIX_SPAWN_OPEN, 2, os.devnull, os.O_WRONLY, 0)])
    signal.setitimer(signal.ITIMER_REAL, SOON, EVERY)
    data = os.read(r, 10)
    log.append("read returned")
    signal.setitimer(signal.ITIMER_REAL, 0)
    os.kill(child, signal.SIGKILL)
    os.waitpid(child, 0)
    return data, left_in(r), taken()


def left_in(r: int) -> bytes:
    os.set_blocking(r, False)
    try:
        rest = os.read(r, 10)
    except BlockingIOError:
        rest = b""
    os.set_blocking(r, True)
    return rest


def blocking_calls() -> None:
    global first, count, arrivals, pipe_end
    # sleep: a handler that returns, and the sleep goes on to its end; a handler that raises, and it does not
    signal.signal(ALRM, note)
    start = time.monotonic()
    signal.setitimer(signal.ITIMER_REAL, SOON)
    slept = m(time.sleep, NAP)
    log.append("sleep returned")
    print("sleep, a handler that returns:", slept, taken(), time.monotonic() - start >= NAP)
    quiet()
    first = True
    signal.signal(ALRM, stops_once)
    start = time.monotonic()
    try:
        signal.setitimer(signal.ITIMER_REAL, SOON, EVERY)
        time.sleep(LONG)
        log.append("the sleep ran out")
    except Stop as e:
        log.append(("out of sleep", e.args))
    quiet()
    print("sleep, a handler that raises:", taken(), time.monotonic() - start < LONG / 2)

    # pause returns once a handler has run
    first = True
    signal.signal(ALRM, once)
    signal.setitimer(signal.ITIMER_REAL, SOON, EVERY)
    paused = m(signal.pause)
    log.append("pause returned")
    quiet()
    print("pause:", paused, taken())
    first = True
    signal.signal(ALRM, stops_once)
    try:
        signal.setitimer(signal.ITIMER_REAL, SOON, EVERY)
        signal.pause()
        log.append("pause returned")
    except Stop as e:
        log.append(("out of pause", e.args))
    quiet()
    print("pause, a handler that raises:", taken(), signal.getitimer(signal.ITIMER_REAL))
    # a timer that repeats: three arrivals, and at most one pause for each
    count = 0
    pauses = 0
    signal.signal(ALRM, counts)
    signal.setitimer(signal.ITIMER_REAL, SOON, EVERY)
    while count < 3 and pauses < 50:
        pauses += 1
        signal.pause()
    print("a timer that repeats:", count, pauses <= 3, signal.getitimer(signal.ITIMER_REAL))
    quiet()

    # a read of an empty pipe. As signal.signal installs a handler, the read is interrupted: the handler runs and writes, and
    # the read is taken up again and finds what the handler wrote. So it is after siginterrupt(True), and after signal.signal
    # installs the handler again, which undoes siginterrupt(False).
    r, pipe_end = os.pipe()
    os.set_blocking(pipe_end, False)
    signal.signal(ALRM, writes_once)
    as_installed = through_a_read(r)
    signal.siginterrupt(ALRM, False)
    signal.siginterrupt(ALRM, True)
    interrupted = through_a_read(r)
    signal.siginterrupt(ALRM, False)
    signal.signal(ALRM, writes_once)
    print("a read that a handler ends:", as_installed, interrupted, through_a_read(r))
    quiet()
    # the same pipe as the wakeup descriptor, so that the signal's own byte ends the read if nothing else does
    signal.set_wakeup_fd(pipe_end)
    signal.signal(ALRM, stops)
    try:
        signal.setitimer(signal.ITIMER_REAL, SOON)
        os.read(r, 10)
        log.append("the read returned")
    except Stop as e:
        log.append(("out of the read", e.args))
    quiet()
    left_in(r)
    print("a read, a handler that raises:", taken(), signal.set_wakeup_fd(-1) == pipe_end)
    os.close(r)
    os.close(pipe_end)

    # a wait for one signal that another signal's handler interrupts goes on: here the handler sends the signal waited for
    signal.signal(U1, note)
    signal.pthread_sigmask(signal.SIG_BLOCK, [U1])
    first = True
    signal.signal(ALRM, sends)
    signal.setitimer(signal.ITIMER_REAL, SOON, EVERY)
    info = signal.sigtimedwait([U1], LONG)
    log.append("the wait returned")
    quiet()
    print("a wait for another signal:", None if info is None else info.si_signo, taken(), sorted([int(s) for s in signal.sigpending()]))
    signal.pthread_sigmask(signal.SIG_UNBLOCK, [U1])
    signal.signal(U1, signal.SIG_DFL)

    # a wait for a lock that is held: the handler lets it go, and the wait gets it
    gate.acquire()
    first = True
    signal.signal(ALRM, releases)
    signal.setitimer(signal.ITIMER_REAL, SOON, EVERY)
    got = gate.acquire(timeout=LONG)
    log.append("acquire returned")
    quiet()
    print("a wait for a lock:", got, taken(), gate.locked())
    if gate.locked():
        gate.release()

    # a wait with a time of its own that a handler interrupts again and again (every EVERY, for LONG) ends at its first
    # deadline, NAP after it began: it is not begun anew after each interruption. What sigtimedwait gives when the deadline
    # passes while a handler runs is not shown (CPython gives what it has not filled in).
    gate.acquire()
    signal.pthread_sigmask(signal.SIG_BLOCK, [U1])
    signal.signal(ALRM, arrives)
    kept: list[tuple[str, str, bool, bool]] = []
    for wait in ("sleep", "acquire", "sigtimedwait"):
        arrivals = 0
        start = time.monotonic()
        signal.setitimer(signal.ITIMER_REAL, SOON, EVERY)
        if wait == "sleep":
            result = m(time.sleep, NAP)
        elif wait == "acquire":
            result = m(gate.acquire, timeout=NAP)
        else:
            signal.sigtimedwait([U1], NAP)
            result = "not shown"
        took = time.monotonic() - start
        signal.setitimer(signal.ITIMER_REAL, 0)
        kept.append((wait, result, took < LONG / 2, arrivals > 0))
    quiet()
    signal.pthread_sigmask(signal.SIG_UNBLOCK, [U1])
    gate.release()
    print("a wait that handlers keep interrupting:", kept)

    # siginterrupt(False) asks the system to start an interrupted call again, but a sleep, a pause and a wait for a lock with
    # a timeout are never started again: the handler runs inside them as before
    first = True
    signal.signal(ALRM, stops_once)
    signal.siginterrupt(ALRM, False)
    start = time.monotonic()
    try:
        signal.setitimer(signal.ITIMER_REAL, SOON, EVERY)
        time.sleep(LONG)
        log.append("the sleep ran out")
    except Stop:
        log.append("out of sleep")
    quiet()
    slept_out = (taken(), time.monotonic() - start < LONG / 2)
    first = True
    signal.signal(ALRM, once)
    signal.siginterrupt(ALRM, False)
    signal.setitimer(signal.ITIMER_REAL, SOON, EVERY)
    signal.pause()
    log.append("pause returned")
    quiet()
    paused_out = taken()
    gate.acquire()
    first = True
    signal.signal(ALRM, releases)
    signal.siginterrupt(ALRM, False)
    signal.setitimer(signal.ITIMER_REAL, SOON, EVERY)
    got = gate.acquire(timeout=LONG)
    log.append("acquire returned")
    quiet()
    print("not started again after siginterrupt(False):", slept_out, paused_out, (got, taken()), gate.locked())
    if gate.locked():
        gate.release()


def main() -> None:
    # nothing is inherited: the mask is emptied, the timers are taken away, and a child's end can be waited for
    signal.pthread_sigmask(signal.SIG_SETMASK, [])
    signal.signal(ALRM, signal.SIG_IGN)
    signal.signal(signal.SIGCHLD, signal.SIG_DFL)
    for which in (signal.ITIMER_REAL, signal.ITIMER_VIRTUAL, signal.ITIMER_PROF):
        signal.setitimer(which, 0)
    code_looks()
    blocking_calls()


if __name__ == "__main__":
    main()
    # a loop in the module's own code, which is no function's
    flag = False
    rounds = 0
    signal.signal(ALRM, sets_flag)
    signal.setitimer(signal.ITIMER_REAL, SOON)
    while not flag and rounds < TURNS:
        rounds += 1
    ended = "ended by the handler" if flag else "gave up"
    quiet()
    print("a loop in the module's own code:", ended, taken(), signal.getitimer(signal.ITIMER_REAL))
