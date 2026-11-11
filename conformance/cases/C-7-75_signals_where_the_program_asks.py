# clause: C-7-75
# spec: section 7
# status: P1
# source: dialect specification sections 3 and 7 (process and signals), Modules/signalmodule.c (signal_signal_impl, signal_getsignal_impl, signal_raise_signal_impl, signal_pthread_kill_impl, signal_pidfd_send_signal_impl, signal_pthread_sigmask_impl, signal_sigpending_impl, signal_sigwait_impl, signal_sigwaitinfo_impl, signal_sigtimedwait_impl, fill_siginfo, signal_set_wakeup_fd_impl, trip_signal, report_wakeup_write_error, signal_siginterrupt_impl, signal_alarm_impl, timeval_from_double, signal_setitimer_impl, signal_getitimer_impl, signal_strsignal_impl, signal_valid_signals_impl, signal_default_int_handler_impl, signal_get_set_handlers, signal_install_handlers, compare_handler, _PyErr_CheckSignalsTstate, PyErr_SetInterruptEx), Modules/clinic/signalmodule.c.h (the order arguments are converted in), Lib/signal.py, Modules/_threadmodule.c (thread_PyThread_interrupt_main), Modules/posixmodule.c (os_kill_impl, os_killpg_impl, _Py_Sigset_Converter), Python/pylifecycle.c (PyOS_setsig)
"""Signals where the program asks for them. A signal the program sends to itself (raise_signal, os.kill, pthread_kill,
pidfd_send_signal, interrupt_main, a mask taken away) has had its handler run when the call returns. What signal.signal
and getsignal say and refuse, what a handler is given, the order of several pending signals, a handler that raises, one
that sends, and one that is changed while its signal waits, SIGINT and KeyboardInterrupt, the waits that take a signal
without its handler (sigwait, sigwaitinfo, sigtimedwait), what the timers answer, the wakeup descriptor, and the names
the two modules have. How arguments are taken: which of two wrong ones is refused, times rounded up before their sign is
tested, alarm's number given to the system unsigned, and the warning for the two numbers the C library keeps, with the
line it is charged to."""
# ruff: noqa: E501
# No clock is waited for: every signal is sent by the program to itself, a signal that must stay pending is blocked first,
# and a timer is set minutes ahead and taken away again. What the process inherited (a shell that starts it in the background
# ignores SIGINT and SIGQUIT, nohup ignores SIGHUP) is set before it is relied on, so the case says the same wherever it is
# started. A handler's frame is asked for its type only, and no signal is left waiting behind a handler that raised.
import _signal  # type: ignore[import-not-found]
import _thread
import atexit
import os
import signal
import sys
import threading
import types
import warnings

U1, U2, TERM, HUP, INT = signal.SIGUSR1, signal.SIGUSR2, signal.SIGTERM, signal.SIGHUP, signal.SIGINT
RT = signal.SIGRTMIN

log: list[object] = []
frames: list[object] = []
depth = 0


def m(f: object, *args: object, **kwargs: object) -> str:
    """What a call gives, or the class of what it raises; an OSError with its number and the system's words for it."""
    try:
        return repr(f(*args, **kwargs)) if callable(f) else "not callable"
    except OSError as e:
        return type(e).__name__ + ": " + repr((e.errno, e.strerror, e.filename))
    except Exception as e:
        return type(e).__name__
    except KeyboardInterrupt as e:
        return "KeyboardInterrupt" + repr(e.args)


def taken() -> list[object]:
    """What the handlers and the program wrote down since the last time."""
    seen = list(log)
    log.clear()
    return seen


def named(handler: object) -> str:
    """A handler without its address."""
    if handler is None:
        return "None"
    if handler is signal.SIG_DFL:
        return "SIG_DFL"
    if handler is signal.SIG_IGN:
        return "SIG_IGN"
    name = getattr(handler, "__name__", None)
    return name if isinstance(name, str) else "a " + type(handler).__name__


def same(a: object, b: object) -> bool:
    return a is b


def equal(a: object, b: object) -> bool:
    return a == b


def pending() -> list[int]:
    return sorted([int(s) for s in signal.sigpending()])


def blocked() -> list[int]:
    return sorted([int(s) for s in signal.pthread_sigmask(signal.SIG_BLOCK, [])])


def charged(caught: list[warnings.WarningMessage]) -> list[tuple[str, str]]:
    """Each warning's class, and the file of the line it is charged to: the program's own, or a module's by its name."""
    here = os.path.basename(__file__)
    return [(w.category.__name__, "the program" if os.path.basename(w.filename) == here else os.path.basename(w.filename)) for w in caught]


def note(signum: int, frame: types.FrameType | None) -> None:
    log.append(signum)


def other(signum: int, frame: types.FrameType | None) -> None:
    log.append(("other", signum))


def given(signum: int, frame: types.FrameType | None) -> None:
    log.append((signum, type(signum).__name__, type(frame).__name__))


def keeps(signum: int, frame: types.FrameType | None) -> None:
    frames.append(frame)


class Stop(Exception):
    pass


def stops(signum: int, frame: types.FrameType | None) -> None:
    log.append(("stops", signum))
    raise Stop(signum)


def out_of(send: object, *args: object) -> None:
    """A call that makes a handler run: whether it returns, or lets out what the handler raised."""
    try:
        if callable(send):
            send(*args)
        log.append("the call returned")
    except Stop as e:
        log.append(("out of the call", e.args))


def again(signum: int, frame: types.FrameType | None) -> None:
    """A handler that sends its own signal: the second is handled inside the first, and the third inside the second."""
    global depth
    depth += 1
    log.append(("in", depth))
    if depth < 3:
        signal.raise_signal(signum)
    log.append(("out", depth))
    depth -= 1


def sends_another(signum: int, frame: types.FrameType | None) -> None:
    log.append("outer in")
    os.kill(os.getpid(), U2)
    log.append("outer out")


def once(signum: int, frame: types.FrameType | None) -> None:
    log.append("once")
    signal.signal(signum, signal.SIG_IGN)


class Called:
    def __init__(self, *seen: object) -> None:
        self.seen = seen

    def __call__(self, signum: int, frame: types.FrameType | None) -> None:
        log.append(("an instance", signum))

    def method(self, signum: int, frame: types.FrameType | None) -> None:
        log.append(("a method", signum))


class Index:
    def __index__(self) -> int:
        return 10


def unraisable(u: sys.UnraisableHookArgs) -> None:
    """What sys.unraisablehook is told, without the words of a built-in exception."""
    e = u.exc_value
    log.append((type(e).__name__, e.errno if isinstance(e, OSError) else None, u.err_msg, u.object))


def at_exit(signum: int, frame: types.FrameType | None) -> None:
    print("at exit, sent by a built-in function that atexit called:", signum, type(frame).__name__, flush=True)


def main() -> None:
    me = os.getpid()
    thread = threading.get_ident()
    valid = sorted([int(s) for s in signal.valid_signals()])

    # what the interpreter itself set when it started, whatever the process inherited: SIGPIPE and SIGXFSZ ignored, and its
    # handler for SIGINT unless SIGINT came ignored. The two numbers the C library keeps for itself have no handler to tell of.
    print("at start:", named(signal.getsignal(signal.SIGPIPE)), named(signal.getsignal(signal.SIGXFSZ)), named(signal.getsignal(INT)) in ("default_int_handler", "SIG_IGN"), signal.getsignal(32), signal.getsignal(33),
          m(signal.getsignal, 0), m(signal.getsignal, signal.NSIG), m(signal.getsignal, -1), m(signal.getsignal, "x"), m(signal.getsignal), m(_signal.getsignal, signalnum=10))
    # from here on nothing is inherited: the signals the case uses, the mask and the timers are set
    for s in (HUP, U1, U2, TERM, signal.SIGCHLD, signal.SIGURG, signal.SIGWINCH, signal.SIGCONT, RT, RT + 1, RT + 2):
        signal.signal(s, signal.SIG_DFL)
    signal.signal(INT, signal.default_int_handler)
    signal.pthread_sigmask(signal.SIG_SETMASK, [])
    signal.alarm(0)
    signal.setitimer(signal.ITIMER_VIRTUAL, 0)
    signal.setitimer(signal.ITIMER_PROF, 0)

    print("numbers:", signal.NSIG, len(valid), valid[0], valid[-1], [n for n in range(1, signal.NSIG) if n not in valid], (int(signal.SIG_DFL), int(signal.SIG_IGN)), (int(signal.SIG_BLOCK), int(signal.SIG_UNBLOCK), int(signal.SIG_SETMASK)),
          (signal.ITIMER_REAL, signal.ITIMER_VIRTUAL, signal.ITIMER_PROF), (int(signal.SIGRTMIN), int(signal.SIGRTMAX)), type(signal.valid_signals()).__name__, sorted([int(n) for n in signal.valid_signals() if type(n).__name__ == "int"])[:3],
          same(signal.valid_signals(), signal.valid_signals()))
    print("as enums:", repr(INT), str(INT), INT.name, repr(signal.SIG_DFL), repr(signal.SIG_IGN), repr(signal.SIG_BLOCK), repr(signal.getsignal(U1)), repr(signal.getsignal(signal.SIGPIPE)), repr(signal.SIGRTMIN), repr(signal.SIGRTMIN + 1),
          same(signal.SIGCLD, signal.SIGCHLD), len(signal.Signals), [s.name for s in signal.Signals], sorted(set(signal.Signals.__members__) - {s.name for s in signal.Signals}), [h.name for h in signal.Handlers], [k.name for k in signal.Sigmasks])
    print("the module underneath:", type(_signal.SIG_DFL).__name__, _signal.SIG_DFL, _signal.SIG_IGN, _signal.getsignal(U1), _signal.getsignal(signal.SIGPIPE), same(_signal.getsignal(INT), _signal.default_int_handler),
          same(signal.default_int_handler, _signal.default_int_handler), equal(sorted(_signal.valid_signals()), valid), same(signal.raise_signal, _signal.raise_signal), same(signal.getsignal, _signal.getsignal),
          same(signal.ItimerError, _signal.ItimerError), signal.ItimerError.__module__, [c.__name__ for c in signal.ItimerError.__mro__[:3]], same(signal.struct_siginfo, _signal.struct_siginfo), signal.struct_siginfo.__module__)
    print("its names:", [n for n in vars(_signal) if not n.startswith("__")], sorted([n for n in vars(_signal) if n.startswith("__")]))
    print("and what they are:", sorted({type(v).__name__ for n, v in vars(_signal).items() if not n.startswith("__")}), len([v for v in vars(_signal).values() if type(v).__name__ == "int"]),
          len([v for v in vars(_signal).values() if type(v).__name__ == "builtin_function_or_method"]), len(vars(_signal)))
    print("strsignal:", [signal.strsignal(n) for n in (1, 2, 9, 10, 13, 14, 15, 17, 31, 32, 33, 34, 64)], m(signal.strsignal, 0), m(signal.strsignal, signal.NSIG), m(signal.strsignal, -1), m(signal.strsignal, "x"), m(signal.strsignal),
          m(signal.strsignal, signalnum=10))

    # signal.signal returns what was there, and getsignal says what is: the very object that was given
    called = Called()
    print("signal.signal returns what was there:", named(signal.signal(U1, note)), named(signal.signal(U1, signal.SIG_IGN)), named(signal.signal(U1, other)), named(signal.signal(U1, signal.SIG_DFL)), named(signal.signal(U1, called)),
          same(signal.getsignal(U1), called), same(signal.signal(U1, called.method), called), equal(signal.getsignal(U1), called.method), named(signal.signal(U1, Called)), same(signal.getsignal(U1), Called), same(signal.signal(U1, print), Called),
          same(signal.signal(U1, signal.SIG_DFL), print), repr(signal.getsignal(U1)), named(signal.signal(INT, signal.SIG_DFL)), repr(signal.signal(INT, signal.default_int_handler)), named(signal.getsignal(INT)))
    # 0 and 1 mean SIG_DFL and SIG_IGN. The signal module makes a number of whatever int() takes, another enum's member
    # and a bool too; the module underneath takes the two as plain ints and nothing else, and gives them back as ints
    print("numbers for handlers:", named(signal.signal(U1, 1)), named(signal.signal(U1, 0)), named(signal.signal(U1, signal.SIG_UNBLOCK)), repr(signal.getsignal(U1)), _signal.getsignal(U1), type(_signal.getsignal(U1)).__name__,
          named(signal.signal(U1, signal.SIG_BLOCK)), named(signal.signal(U1, True)), named(signal.signal(U1, False)), m(_signal.signal, U1, True), m(_signal.signal, U1, signal.SIG_IGN), m(_signal.signal, U1, 1), m(_signal.signal, U1, 0),
          m(signal.signal, U1, 2), m(signal.signal, U1, -1), m(signal.signal, U1, 2**70), m(signal.signal, Index(), signal.SIG_DFL), repr(signal.getsignal(U1)))
    print("signal.signal refuses:", m(signal.signal, 0, note), m(signal.signal, -1, note), m(signal.signal, signal.NSIG, note), m(signal.signal, 2**40, note), m(signal.signal, "x", note), m(signal.signal, U1, 5), m(signal.signal, U1, None),
          m(signal.signal, U1, "x"), m(signal.signal, U1), m(signal.signal, U1, note, 1), m(_signal.signal, U1, handler=note), m(signal.signal, signal.SIGKILL, note), m(signal.signal, signal.SIGSTOP, signal.SIG_IGN),
          m(signal.signal, signal.SIGKILL, signal.SIG_DFL), m(signal.signal, 32, note), m(signal.signal, 33, signal.SIG_DFL), repr(signal.getsignal(U1)), repr(signal.getsignal(signal.SIGKILL)), repr(signal.getsignal(signal.SIGSTOP)), signal.getsignal(32))

    # a signal the program sends to itself: its handler has run when the call returns. The handler is given the number as an
    # int, whatever was sent, and the frame that was running
    signal.signal(U1, given)
    signal.raise_signal(U1)
    os.kill(me, signal.Signals.SIGUSR1)
    signal.pthread_kill(thread, U1)
    print("what a handler is given:", taken())
    signal.signal(U1, note)
    signal.raise_signal(U1)
    log.append("raise_signal returned")
    os.kill(me, U1)
    log.append("os.kill returned")
    signal.pthread_kill(thread, U1)
    log.append("pthread_kill returned")
    print("the handler has run when the call returns:", taken(), m(signal.raise_signal, U1), m(os.kill, me, U1), m(signal.pthread_kill, thread, U1), taken())
    signal.signal(U1, called)
    signal.raise_signal(U1)
    signal.signal(U1, called.method)
    signal.raise_signal(U1)
    print("handlers that are not functions:", taken())
    signal.signal(U1, signal.SIG_IGN)
    print("ignored, and those the system ignores:", m(signal.raise_signal, U1), m(os.kill, me, U1), m(signal.raise_signal, signal.SIGCHLD), m(signal.raise_signal, signal.SIGURG), m(signal.raise_signal, signal.SIGWINCH), m(signal.raise_signal, signal.SIGCONT),
          m(signal.raise_signal, signal.SIGPIPE), m(signal.raise_signal, signal.SIGXFSZ), m(signal.raise_signal, 0), m(os.kill, me, 0), m(signal.pthread_kill, thread, 0), taken())
    print("sending refuses:", m(signal.raise_signal, -1), m(signal.raise_signal, signal.NSIG), m(signal.raise_signal, 32), m(signal.raise_signal, 33), m(signal.raise_signal, 2**40), m(signal.raise_signal, "x"), m(signal.raise_signal),
          m(_signal.raise_signal, signalnum=10), m(os.kill, me, signal.NSIG), m(os.kill, me, -1), m(os.kill, 2**30, 0), m(os.kill, me), m(os.kill, "x", 0), m(os.kill, pid=me, signal=0), m(signal.pthread_kill, thread, signal.NSIG),
          m(signal.pthread_kill, thread, -1), m(signal.pthread_kill, thread, 32), m(signal.pthread_kill, thread), m(signal.pthread_kill, "x", 10), m(signal.pthread_kill, thread, 2**40), taken())

    # the same through a descriptor for the process
    pidfd = os.pidfd_open(me)
    signal.signal(U1, note)
    signal.pidfd_send_signal(pidfd, U1)
    log.append("pidfd_send_signal returned")
    signal.signal(U1, stops)
    out_of(signal.pidfd_send_signal, pidfd, U1)
    print("pidfd_send_signal:", taken(), m(signal.pidfd_send_signal, pidfd, 0), m(signal.pidfd_send_signal, pidfd, signal.NSIG), m(signal.pidfd_send_signal, pidfd, -1), m(signal.pidfd_send_signal, pidfd, 0, None, -1),
          m(signal.pidfd_send_signal, pidfd, 0, 5), m(signal.pidfd_send_signal, pidfd), m(signal.pidfd_send_signal, "x", 0), m(signal.pidfd_send_signal, pidfd=pidfd, signalnum=0), m(signal.pidfd_send_signal, -1, 0), m(os.close, pidfd),
          m(signal.pidfd_send_signal, pidfd, 0), taken())

    # _thread.interrupt_main makes a signal arrive without sending it: a mask does not hold it back, and a signal that is
    # ignored or has its default action is left alone. A number that has no handler to call is reported and passed over.
    signal.signal(U1, note)
    signal.pthread_sigmask(signal.SIG_BLOCK, [U1])
    _thread.interrupt_main(U1)
    log.append("interrupt_main returned")
    held_back = pending()
    signal.pthread_sigmask(signal.SIG_UNBLOCK, [U1])
    signal.signal(U1, stops)
    out_of(_thread.interrupt_main, U1)
    signal.signal(U1, signal.SIG_IGN)
    left_alone = [m(_thread.interrupt_main, U1)]
    signal.signal(U1, signal.SIG_DFL)
    left_alone.append(m(_thread.interrupt_main, U1))
    sys.unraisablehook = unraisable
    left_alone.append(m(_thread.interrupt_main, 32))
    sys.unraisablehook = sys.__unraisablehook__
    print("interrupt_main:", taken(), held_back, left_alone, m(_thread.interrupt_main), m(_thread.interrupt_main, INT), m(_thread.interrupt_main, 0), m(_thread.interrupt_main, signal.NSIG), m(_thread.interrupt_main, -1),
          m(_thread.interrupt_main, "x"), m(_thread.interrupt_main, signum=2), m(_thread.interrupt_main, 2, 3))

    # several signals pending at once: blocked, raised in another order, the mask taken away. The handlers run in the order of
    # the numbers, each once however often its signal was raised, inside the call that unblocks them.
    every = [U1, U2, TERM, HUP, RT, RT + 1]
    for s in every:
        signal.signal(s, note)
    old = signal.pthread_sigmask(signal.SIG_BLOCK, every)
    for s in (RT + 1, TERM, U2, HUP, U1, RT, U1, U1, RT, RT):
        signal.raise_signal(s)
    waiting = (pending(), taken())
    back = signal.pthread_sigmask(signal.SIG_UNBLOCK, every)
    log.append("unblocked")
    print("blocked, raised, unblocked:", sorted(old), waiting, taken(), sorted([int(s) for s in back]), pending(), blocked())
    signal.pthread_sigmask(signal.SIG_BLOCK, [U1, U2, TERM])
    for s in (U1, U2, TERM):
        os.kill(me, s)
    signal.pthread_sigmask(signal.SIG_UNBLOCK, [U2])
    log.append("SIGUSR2 unblocked")
    signal.pthread_sigmask(signal.SIG_UNBLOCK, [TERM])
    log.append("SIGTERM unblocked")
    signal.pthread_sigmask(signal.SIG_SETMASK, [])
    log.append("the mask emptied")
    print("one at a time:", taken())
    signal.signal(U1, keeps)
    signal.signal(U2, keeps)
    signal.pthread_sigmask(signal.SIG_BLOCK, [U1, U2])
    signal.raise_signal(U2)
    signal.raise_signal(U1)
    signal.pthread_sigmask(signal.SIG_UNBLOCK, [U1, U2])
    print("two handlers in one go are given one frame:", len(frames), same(frames[0], frames[1]), type(frames[0]).__name__)
    frames.clear()
    print("the mask:", blocked(), sorted(signal.pthread_sigmask(signal.SIG_BLOCK, [U1, 40])), sorted([(type(s).__name__, int(s)) for s in signal.pthread_sigmask(signal.SIG_BLOCK, (U2,))]), sorted(_signal.pthread_sigmask(signal.SIG_SETMASK, {TERM})),
          sorted(_signal.pthread_sigmask(signal.SIG_SETMASK, [signal.SIGKILL, signal.SIGSTOP, U1])), sorted(_signal.pthread_sigmask(signal.SIG_SETMASK, [])), type(_signal.pthread_sigmask(signal.SIG_BLOCK, [])).__name__,
          type(signal.pthread_sigmask(signal.SIG_BLOCK, [])).__name__, m(signal.pthread_sigmask, signal.SIG_BLOCK, [0]), m(signal.pthread_sigmask, signal.SIG_BLOCK, [signal.NSIG]), m(signal.pthread_sigmask, signal.SIG_BLOCK, [U1, "x"]),
          m(signal.pthread_sigmask, signal.SIG_BLOCK, 5), m(signal.pthread_sigmask, 3, []), m(signal.pthread_sigmask, signal.SIG_BLOCK), blocked(), type(_signal.sigpending()).__name__, m(signal.sigpending), m(_signal.sigpending, 1))
    # 32 and 33 in a set are passed over with a RuntimeWarning, charged to the innermost line of Python: the signal module's
    # own for its wrapper, the program's for the module underneath and for the functions the signal module takes from it as
    # they are. Made an error, the warning ends the call before anything is changed.
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        before = signal.pthread_sigmask(signal.SIG_BLOCK, [32, U1, 33])
        now = blocked()
        _signal.pthread_sigmask(signal.SIG_BLOCK, [U2, 33])
        signal.sigtimedwait([32], 0)
        now_too = blocked()
    signal.pthread_sigmask(signal.SIG_SETMASK, [])
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        made_errors = (m(signal.pthread_sigmask, signal.SIG_BLOCK, [U1, 32, U2]), m(_signal.pthread_sigmask, signal.SIG_BLOCK, [U1, 33]), m(signal.sigwait, [32, 0]), m(signal.sigtimedwait, [U1, 33], 0))
        still = blocked()
    print("the two numbers the C library keeps:", sorted(before), now, now_too, charged(caught), made_errors, still)

    # a handler that raises: the exception comes out of the call that made it run, and those with lower numbers have run
    signal.signal(U1, stops)
    out_of(signal.raise_signal, U1)
    out_of(os.kill, me, U1)
    out_of(signal.pthread_kill, thread, U1)
    signal.signal(HUP, note)
    signal.pthread_sigmask(signal.SIG_BLOCK, [HUP, U1])
    signal.raise_signal(U1)
    signal.raise_signal(HUP)
    out_of(signal.pthread_sigmask, signal.SIG_UNBLOCK, [HUP, U1])
    print("a handler that raises:", taken(), blocked(), pending())

    # a handler that sends: its own signal again (handled inside itself), and another one
    signal.signal(U1, again)
    signal.raise_signal(U1)
    nested = taken()
    signal.signal(U1, sends_another)
    signal.signal(U2, other)
    signal.raise_signal(U1)
    print("a handler that sends:", nested, taken())
    signal.signal(U1, once)
    signal.raise_signal(U1)
    signal.raise_signal(U1)
    print("a handler that takes itself away:", taken(), repr(signal.getsignal(U1)))

    # a signal's handler is changed while the signal is pending: the new one runs. Ignoring a pending signal discards it;
    # the default action for it does not, and a handler set afterwards still gets it
    signal.signal(U1, note)
    signal.pthread_sigmask(signal.SIG_BLOCK, [U1])
    signal.raise_signal(U1)
    was = signal.signal(U1, other)
    log.append(("replaced while pending", same(was, note), pending()))
    signal.pthread_sigmask(signal.SIG_UNBLOCK, [U1])
    replaced = taken()
    signal.pthread_sigmask(signal.SIG_BLOCK, [U1])
    signal.raise_signal(U1)
    signal.signal(U1, signal.SIG_IGN)
    log.append(("ignored while pending", pending()))
    signal.signal(U1, note)
    signal.pthread_sigmask(signal.SIG_UNBLOCK, [U1])
    ignored = taken()
    signal.pthread_sigmask(signal.SIG_BLOCK, [U1])
    signal.raise_signal(U1)
    signal.signal(U1, signal.SIG_DFL)
    log.append(("default while pending", pending()))
    signal.signal(U1, other)
    signal.pthread_sigmask(signal.SIG_UNBLOCK, [U1])
    print("changed while pending:", replaced, ignored, taken())

    # SIGINT: the handler Python has for it raises KeyboardInterrupt, out of the call that sent the signal
    try:
        signal.raise_signal(INT)
        interrupted: object = "not raised"
    except Exception:
        interrupted = "an Exception"
    except KeyboardInterrupt as e:
        interrupted = (type(e).__name__, e.args, e.__context__, e.__cause__)
    print("SIGINT:", interrupted, m(signal.raise_signal, INT), m(os.kill, me, INT), m(signal.pthread_kill, thread, INT), m(signal.default_int_handler, 2, None), m(signal.default_int_handler, 0, None), m(signal.default_int_handler, 99999, "anything"),
          m(signal.default_int_handler), m(signal.default_int_handler, 2), m(signal.default_int_handler, 2, None, 3), m(signal.default_int_handler, "x", None), m(signal.default_int_handler, 2.0, None), m(signal.default_int_handler, 2**40, None),
          m(signal.default_int_handler, signalnum=2, frame=None), type(signal.default_int_handler).__name__, signal.default_int_handler.__name__, signal.default_int_handler.__module__, issubclass(KeyboardInterrupt, Exception),
          KeyboardInterrupt.__mro__[1].__name__)
    signal.signal(INT, note)
    signal.raise_signal(INT)
    signal.signal(INT, signal.SIG_IGN)
    signal.raise_signal(INT)
    print("SIGINT with another handler, and ignored:", taken(), named(signal.signal(INT, signal.default_int_handler)))

    # the timers: what they answer. They are set minutes ahead and taken away again; none of them fires.
    first = signal.alarm(1000)
    second = signal.alarm(500)
    third = signal.alarm(0)
    print("alarm:", first, 990 < second <= 1000, 490 < third <= 500, signal.alarm(0), type(third).__name__, m(signal.alarm), m(signal.alarm, 1.5), m(signal.alarm, "x"), m(signal.alarm, 2**31), m(_signal.alarm, seconds=1000), signal.alarm(0))
    # alarm takes a C int and hands it to the system as an unsigned one: -1 is the longest alarm there is
    print("alarm with a negative number:", signal.alarm(-1), 2**32 - 60 < signal.alarm(0) <= 2**32 - 1, signal.alarm(-2**31), 2**31 - 60 < signal.alarm(0) <= 2**31, m(signal.alarm, 2**32 - 1), m(signal.alarm, -2**31 - 1), signal.alarm(0))
    idle = signal.getitimer(signal.ITIMER_REAL)
    was_idle = signal.setitimer(signal.ITIMER_REAL, 1000, 7.5)
    running = signal.getitimer(signal.ITIMER_REAL)
    stopped = signal.setitimer(signal.ITIMER_REAL, 0)
    signal.alarm(1000)
    by_alarm = signal.getitimer(signal.ITIMER_REAL)
    signal.setitimer(signal.ITIMER_REAL, 999.5)
    by_timer = signal.alarm(0)
    print("setitimer and getitimer:", idle, was_idle, 990 < running[0] <= 1000, running[1], 990 < stopped[0] <= 1000, stopped[1], signal.getitimer(signal.ITIMER_REAL), [type(x).__name__ for x in stopped], type(stopped).__name__,
          990 < by_alarm[0] <= 1000, by_alarm[1], 990 < by_timer <= 1000, signal.setitimer(signal.ITIMER_VIRTUAL, 1000, 2), signal.setitimer(signal.ITIMER_VIRTUAL, 0)[1], signal.setitimer(signal.ITIMER_PROF, 1000, 3),
          signal.setitimer(signal.ITIMER_PROF, 0, 0)[1], signal.setitimer(signal.ITIMER_REAL, 600), 590 < signal.setitimer(signal.ITIMER_REAL, 0)[0] <= 600,
          signal.getitimer(signal.ITIMER_REAL), signal.getitimer(signal.ITIMER_VIRTUAL), signal.getitimer(signal.ITIMER_PROF))
    print("the timers refuse:", m(signal.setitimer, 99, 1000), m(signal.getitimer, 99), m(signal.getitimer, -1), m(signal.setitimer, signal.ITIMER_REAL, -1000), m(signal.setitimer, signal.ITIMER_REAL, 1000, -1), m(signal.setitimer, signal.ITIMER_REAL),
          m(signal.setitimer, "x", 1000), m(signal.setitimer, signal.ITIMER_REAL, "x"), m(signal.setitimer, signal.ITIMER_REAL, 1000, "x"), m(signal.setitimer, signal.ITIMER_REAL, None), m(signal.setitimer, signal.ITIMER_REAL, float("nan")),
          m(signal.setitimer, signal.ITIMER_REAL, float("inf")), m(signal.setitimer, signal.ITIMER_REAL, 1000, 2, 3), m(_signal.setitimer, which=0, seconds=1000), m(signal.getitimer), m(signal.getitimer, "x"), signal.getitimer(signal.ITIMER_REAL),
          issubclass(signal.ItimerError, OSError))
    # a time is rounded up to the microsecond (setitimer) or the nanosecond (sigtimedwait) before its sign is tested, so a
    # little less than nothing is nothing; the interval comes back as it was rounded
    print("times are rounded up:", signal.setitimer(signal.ITIMER_REAL, 1000, 1e-7), signal.setitimer(signal.ITIMER_REAL, 0)[1], signal.setitimer(signal.ITIMER_REAL, 1000, 1.0000001), signal.setitimer(signal.ITIMER_REAL, 0)[1],
          signal.setitimer(signal.ITIMER_REAL, 1000, 2**-30), signal.setitimer(signal.ITIMER_REAL, 0)[1], m(signal.setitimer, signal.ITIMER_REAL, -1e-7), m(signal.setitimer, signal.ITIMER_REAL, -1e-6), m(signal.setitimer, signal.ITIMER_REAL, 1000, -1e-7),
          signal.setitimer(signal.ITIMER_REAL, 0)[1], signal.getitimer(signal.ITIMER_REAL), m(signal.sigtimedwait, [U1], -1e-10), m(signal.sigtimedwait, [U1], -1e-9), m(signal.sigtimedwait, [U1], -2e-9))

    # the wakeup descriptor: one byte, the signal's number, for every signal that has a handler, written when it arrives
    r, w = os.pipe()
    blocking = m(signal.set_wakeup_fd, w)
    os.set_blocking(r, False)
    os.set_blocking(w, False)
    gone, gone_too = os.pipe()
    os.close(gone)
    os.close(gone_too)
    for s in every:
        signal.signal(s, note)
    print("set_wakeup_fd:", signal.set_wakeup_fd(-1), blocking, signal.set_wakeup_fd(w), signal.set_wakeup_fd(w) == w, signal.set_wakeup_fd(w, warn_on_full_buffer=False) == w, m(signal.set_wakeup_fd, gone), m(signal.set_wakeup_fd, -2),
          m(signal.set_wakeup_fd), m(signal.set_wakeup_fd, "x"), m(signal.set_wakeup_fd, w, True), m(signal.set_wakeup_fd, w, warn=True), m(signal.set_wakeup_fd, 2**40), signal.set_wakeup_fd(w) == w)
    signal.raise_signal(U1)
    one = os.read(r, 100)
    for s in (U2, U1, TERM, RT + 1, RT):
        signal.raise_signal(s)
    several = os.read(r, 100)
    arrived = taken()
    signal.pthread_sigmask(signal.SIG_BLOCK, [U1, U2, TERM])
    for s in (TERM, U2, U1):
        signal.raise_signal(s)
    signal.pthread_sigmask(signal.SIG_UNBLOCK, [U1, U2, TERM])
    together = sorted(os.read(r, 100))
    signal.signal(U1, signal.SIG_IGN)
    signal.raise_signal(U1)
    signal.raise_signal(signal.SIGCHLD)
    nothing = m(os.read, r, 100)
    signal.signal(U1, stops)
    out_of(signal.raise_signal, U1)
    print("what is written:", one, several, arrived, together, taken(), nothing, os.read(r, 100))
    # interrupt_main sends nothing, but the signal it makes arrive writes its byte all the same; one that is ignored or has
    # its default action is passed over and writes nothing
    signal.signal(U1, note)
    _thread.interrupt_main(U1)
    by_interrupt = os.read(r, 100)
    signal.signal(U1, signal.SIG_IGN)
    _thread.interrupt_main(U1)
    signal.signal(U1, signal.SIG_DFL)
    _thread.interrupt_main(U1)
    passed_over = m(os.read, r, 100)
    _thread.interrupt_main(U2)
    _thread.interrupt_main(HUP)
    print("interrupt_main writes it too:", by_interrupt, passed_over, os.read(r, 100), taken())
    # a byte that cannot be written is reported to sys.unraisablehook, where the program's code next looks for signals: in
    # the handler, before its first line. A full pipe is reported unless the program asked not to be told
    # (warn_on_full_buffer, which is taken by its truth); any other failure always is.
    sys.unraisablehook = unraisable
    signal.signal(U1, note)
    while m(os.write, w, b"x" * 4096) == "4096":
        pass
    while m(os.write, w, b"x") == "1":
        pass
    signal.raise_signal(U1)
    full = taken()
    told: list[tuple[str, list[object]]] = []
    asked: tuple[object, ...] = ([], "x", 2, 0)
    for warn in asked:
        m(signal.set_wakeup_fd, w, warn_on_full_buffer=warn)
        signal.raise_signal(U1)
        told.append((repr(warn), [x[0] if isinstance(x, tuple) else x for x in taken()]))
    print("told of a full pipe:", told)
    signal.set_wakeup_fd(w, warn_on_full_buffer=False)
    signal.raise_signal(U1)
    full_unsaid = taken()
    os.close(r)
    os.close(w)
    signal.raise_signal(U1)
    print("a byte that cannot be written:", full, full_unsaid, taken(), signal.set_wakeup_fd(-1) == w, signal.set_wakeup_fd(-1), m(signal.set_wakeup_fd, w))
    sys.unraisablehook = sys.__unraisablehook__
    signal.raise_signal(U1)
    print("no descriptor, nothing to write:", taken())

    # the waits take a pending signal without its handler: the lowest number first
    signal.signal(U1, note)
    signal.signal(U2, note)
    signal.signal(RT + 2, note)
    signal.pthread_sigmask(signal.SIG_BLOCK, [U1, U2, RT + 2])
    signal.raise_signal(U2)
    signal.raise_signal(U1)
    lowest = signal.sigwait([U1, U2])
    signal.raise_signal(RT + 2)
    unnamed = signal.sigwait([RT + 2])
    print("sigwait:", repr(lowest), repr(signal.sigwait({U1, U2})), pending(), taken(), repr(unnamed), m(signal.raise_signal, U1), _signal.sigwait([U1]), m(signal.sigwait, 5), m(signal.sigwait, [0]), m(signal.sigwait, [signal.NSIG]), m(signal.sigwait, ["x"]),
          m(signal.sigwait), m(_signal.sigwait, sigset=[U1]))
    os.kill(me, U1)
    info = signal.sigwaitinfo([U1])
    signal.raise_signal(U2)
    timed = signal.sigtimedwait([U1, U2], 10)
    print("sigwaitinfo and sigtimedwait:", type(info).__name__, type(info).__module__, len(info), info.si_signo, info.si_code, info.si_errno, info.si_pid == me, info.si_uid == os.getuid(), info.si_status, isinstance(info, tuple), info[0], info[:3],
          same(type(info), signal.struct_siginfo), None if timed is None else (timed.si_signo, timed.si_errno, timed.si_pid == me, timed.si_uid == os.getuid(), timed.si_status), signal.sigtimedwait([U1, U2], 0), signal.sigtimedwait([U1, U2], 0.01),
          signal.sigtimedwait([], 0), signal.sigtimedwait([signal.SIGKILL], 0), taken(), pending())
    print("the waits refuse:", m(signal.sigtimedwait, [U1], -1), m(signal.sigtimedwait, [U1], -0.001), m(signal.sigtimedwait, [U1], "x"), m(signal.sigtimedwait, [U1], None), m(signal.sigtimedwait, [U1]), m(signal.sigtimedwait, [U1], float("nan")),
          m(signal.sigtimedwait, [U1], float("inf")), m(signal.sigtimedwait, 5, 0), m(signal.sigtimedwait, [0], 0), m(signal.sigwaitinfo, 5), m(signal.sigwaitinfo, [signal.NSIG]), m(signal.sigwaitinfo), m(_signal.sigtimedwait, sigset=[U1], timeout=0),
          m(signal.struct_siginfo, (1, 2)))
    # a real-time signal is kept once for each time it was sent, another signal once; and a signal that would end the program
    # is taken like any other
    for _ in range(3):
        signal.raise_signal(U1)
        signal.raise_signal(RT + 2)
    queued = [signal.sigtimedwait([RT + 2], 0) is not None for _ in range(4)]
    kept = [signal.sigtimedwait([U1], 0) is not None for _ in range(2)]
    signal.signal(TERM, signal.SIG_DFL)
    signal.pthread_sigmask(signal.SIG_BLOCK, [TERM])
    signal.raise_signal(TERM)
    fatal = (pending(), repr(signal.sigwait([TERM])))
    signal.signal(TERM, note)
    signal.pthread_sigmask(signal.SIG_SETMASK, [])
    print("what queues, and a signal that would have ended the program:", queued, kept, fatal, taken(), pending(), blocked())

    # siginterrupt says whether a system call that a handler interrupted is started again by the system; here only what it takes
    print("siginterrupt:", m(signal.siginterrupt, U1, False), m(signal.siginterrupt, U1, True), m(signal.siginterrupt, U1, 5), m(signal.siginterrupt, signal.SIGPIPE, True), repr(signal.getsignal(signal.SIGPIPE)), named(signal.getsignal(U1)),
          m(signal.siginterrupt, 0, True), m(signal.siginterrupt, signal.NSIG, True), m(signal.siginterrupt, signal.SIGKILL, True), m(signal.siginterrupt, 32, True), m(signal.siginterrupt, U1), m(signal.siginterrupt, "x", True),
          m(signal.siginterrupt, U1, "x"), m(signal.siginterrupt, U1, None), m(signal.siginterrupt, U1, 1.0), m(signal.siginterrupt, U1, 2**40), m(_signal.siginterrupt, signalnum=10, flag=True))

    # two things wrong at once: which one is refused. signal.signal tests the number's range, then the handler, then asks the
    # system; siginterrupt and setitimer convert every argument before a range is tested or the system asked; a set is read
    # before a timeout or how a mask is to change (a warning for 32 comes before the refusal of a later number); pidfd_send_signal
    # refuses a siginfo before it asks the system, which tests the flags before the descriptor
    with warnings.catch_warnings(record=True) as warned:
        warnings.simplefilter("always")
        print("which check comes first:", m(signal.signal, 0, "x"), m(_signal.signal, 0, "x"), m(signal.signal, signal.SIGKILL, "x"), m(signal.signal, 32, "x"), m(signal.signal, signal.NSIG, 5), m(_signal.signal, 2**40, "x"), m(_signal.signal, "x", 2**40),
              m(signal.siginterrupt, 0, "x"), m(signal.siginterrupt, signal.NSIG, None), m(signal.siginterrupt, "x", "y"), m(signal.setitimer, 99, "x"), m(signal.setitimer, 99, float("nan")), m(signal.setitimer, 99, 1000, "x"),
              m(signal.setitimer, signal.ITIMER_REAL, "x", float("nan")), m(signal.setitimer, signal.ITIMER_REAL, float("nan"), "x"), m(signal.setitimer, "x", "y"), m(signal.sigtimedwait, [0], -1), m(signal.sigtimedwait, [0], "x"),
              m(signal.sigtimedwait, ["x"], float("nan")), m(signal.sigtimedwait, 5, -1), m(signal.pthread_sigmask, 3, [0]), m(signal.pthread_sigmask, "x", [0]), m(signal.pthread_sigmask, signal.SIG_BLOCK, [32, 0]),
              m(signal.pthread_sigmask, signal.SIG_BLOCK, [2**70]), m(signal.pthread_sigmask, signal.SIG_BLOCK, [10.0]), m(signal.pthread_sigmask, signal.SIG_BLOCK, [-1]), m(signal.pthread_sigmask, 3, [32]), m(signal.pidfd_send_signal, -1, 0, 5),
              m(signal.pidfd_send_signal, -1, 0, None, "x"), m(signal.pidfd_send_signal, -1, 2**40), m(signal.pidfd_send_signal, -1, 0, None, -1), m(signal.pidfd_send_signal, -1, 0, None, 0), m(signal.set_wakeup_fd, "x", warn_on_full_buffer=5),
              m(signal.set_wakeup_fd, fd=-1), m(signal.set_wakeup_fd, 1.0), blocked(), signal.getitimer(signal.ITIMER_REAL), charged(warned))

    # a process group: only what killpg refuses, so that nobody else is told anything
    print("killpg refuses:", m(os.killpg, 2**30, 0), m(os.killpg, 0, signal.NSIG), m(os.killpg, 0, -1), m(os.killpg, -5, 0), m(os.killpg, 0), m(os.killpg, "x", 0), m(os.killpg, 0, "x"), m(os.killpg, 2**40, 0), m(os.killpg, pgid=0, signal=0))

    # the end: a handler that is called when no code of the program is running is given None for the frame
    signal.signal(U2, at_exit)
    atexit.register(print, "atexit: registered first, runs last")
    atexit.register(signal.raise_signal, U2)
    print("the main body ends")


if __name__ == "__main__":
    main()
