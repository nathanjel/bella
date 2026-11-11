"""_signal, in Python over the runtime's signal core (runtime/src/signals.cpp), from Modules/signalmodule.c and its clinic
(Modules/clinic/signalmodule.c.h), with _Py_Sigset_Converter (Modules/posixmodule.c) and the conversions of seconds
(Python/pytime.c); see posix.py beside it. The numbers are the pin's, Linux's, written here once, as errno.py's are, but
SIGRTMIN and SIGRTMAX, which the C library decides when the program starts. The docstrings are the names table's rows.

Each function parses its arguments here, in the C's order and words, and a primitive makes one system call: it gives what the
call gave, or a negative errno. The table of handlers, the notes a signal leaves and the looks that run a handler are the
runtime's (signals.cpp): `_signals("check")` is PyErr_CheckSignals where the C calls it itself, and `_signals("look")` is the
look CPython's evaluation loop takes when a call of a C function is over (`_CHECK_PERIODIC_AT_END`): the functions that send
a signal or wait end with it (and those that call PyErr_CheckSignals themselves take it after that), and a function that
waits also takes it before it waits (docs/DECISIONS.md, 2026-11-11). The runtime imports this module when it starts
(_PySignal_Init) and empties the table when the program is over (_PySignal_Fini); one thread, so the two "only works in main
thread of the main interpreter" refusals have nowhere to happen.

The primitives, all through `_signals(name, ...)`:
    "rt"                                      (SIGRTMIN, SIGRTMAX), the C library's
    "exec", default_int_handler               signal_get_set_handlers: the table from the dispositions the program was started
                                              with, and SIGINT's handler if it was the default's (an exact build only)
    "check" / "look"                          PyErr_CheckSignals / the look when a call is over (look_if_noted)
    "handler", signum                         the table's entry, None for an empty one
    "signal", signum, how, handler            PyOS_setsig (how: 0 SIG_DFL, 1 SIG_IGN, 2 the runtime's C handler), then the
                                              entry exchanged: (the old entry or None,), or -errno with nothing changed
    "interrupt", signum                       PyErr_SetInterruptEx, for _thread.interrupt_main
    "alarm", seconds                          what alarm() gave, as a C long
    "pause"                                   pause()
    "raise", signum                           raise(): 0 or -errno
    "strsignal", signum                       the C library's text, None where it has none
    "siginterrupt", signum, flag              SA_RESTART cleared or set: 0 or -errno
    "fstat", fd / "blocking", fd              0 or -errno / 1, 0 or -errno
    "wakeup", fd, warn                        the wakeup descriptor and its flag stored: the old descriptor
    "setitimer", which, sec, usec, sec, usec  (sec, usec, sec, usec) of the old timer, or -errno; "getitimer", which
    "sigaddset", number                       0, or the errno sigaddset gave for a number the C library keeps
    "sigmask", how, numbers                   the old mask's numbers in order, or -errno
    "sigpending" / "sigfillset"               a set's numbers in order, or -errno
    "sigwait", numbers                        the number, or -errno
    "sigwaitinfo", numbers                    one call: siginfo_t's seven as fill_siginfo reads them, or -errno (EINTR among them)
    "sigtimedwait", numbers, sec, nsec        the same with a timeout
    "pthread_kill", thread_id, signum         0 or -errno; a thread that is not the calling one stops by name
    "pidfd_send_signal", pidfd, signum, flags 0 or -errno
    "strerror", code / "monotonic"            the C library's text / the monotonic clock in nanoseconds
    "interrupt", signum / "wait", deadline    _thread's: PyErr_SetInterruptEx / a lock's wait to a monotonic deadline, which a
                                              signal ends after Py_MakePendingCalls (1), or the deadline (0)
"""

__all__ = ["default_int_handler", "alarm", "setitimer", "getitimer", "signal", "raise_signal", "strsignal", "getsignal", "set_wakeup_fd",
           "siginterrupt", "pause", "pidfd_send_signal", "pthread_kill", "pthread_sigmask", "sigpending", "sigwait", "sigwaitinfo",
           "sigtimedwait", "valid_signals", "NSIG", "SIG_BLOCK", "SIG_UNBLOCK", "SIG_SETMASK", "SIGHUP", "SIGINT", "SIGQUIT", "SIGILL",
           "SIGTRAP", "SIGIOT", "SIGABRT", "SIGFPE", "SIGKILL", "SIGBUS", "SIGSEGV", "SIGSYS", "SIGPIPE", "SIGALRM", "SIGTERM", "SIGUSR1",
           "SIGUSR2", "SIGCLD", "SIGCHLD", "SIGPWR", "SIGIO", "SIGURG", "SIGWINCH", "SIGPOLL", "SIGSTOP", "SIGTSTP", "SIGCONT", "SIGTTIN",
           "SIGTTOU", "SIGVTALRM", "SIGPROF", "SIGXCPU", "SIGXFSZ", "SIGRTMIN", "SIGRTMAX", "SIGSTKFLT", "ITIMER_REAL", "ITIMER_VIRTUAL",
           "ITIMER_PROF", "SIG_DFL", "SIG_IGN", "ItimerError", "struct_siginfo"]   # vars(_signal)'s order on the pin: `from _signal import *` copies in it

__name__ = "_signal"

try:
    _number_index                                # noqa: B018  # PyNumber_Index, given by the runtime
    _as_double                                   # noqa: B018  # PyFloat_AsDouble, with its messages
    _unpack_keywords                             # noqa: B018  # _PyArg_UnpackKeywords
    _tp_name                                     # noqa: B018  # Py_TYPE(obj)->tp_name
    _structseq                                   # noqa: B018  # bootstrap.py's: a type of named tuples
    _warn                                        # noqa: B018  # PyErr_WarnEx(category, message, 1): a message and the category's name
    _signals                                     # noqa: B018  # the runtime's signal core, by name (runtime/src/signals.cpp)
except NameError:
    from collections.abc import Callable
    from typing import Any

    def _missing(*args: object) -> Any:
        raise ImportError("this file needs the runtime's primitives")

    _number_index: Callable[..., int] = _missing
    _as_double: Callable[..., float] = _missing
    _unpack_keywords: Callable[..., Any] = _missing
    _tp_name: Callable[..., str] = _missing
    _structseq: Callable[..., Any] = _missing
    _warn: Callable[..., Any] = _missing
    _signals: Callable[..., Any] = _missing

NSIG = 65                                        # Py_NSIG: a signal's number is 1 to 64
SIG_BLOCK = 0
SIG_UNBLOCK = 1
SIG_SETMASK = 2
SIGHUP = 1
SIGINT = 2
SIGQUIT = 3
SIGILL = 4
SIGTRAP = 5
SIGIOT = 6
SIGABRT = 6
SIGFPE = 8
SIGKILL = 9
SIGBUS = 7
SIGSEGV = 11
SIGSYS = 31
SIGPIPE = 13
SIGALRM = 14
SIGTERM = 15
SIGUSR1 = 10
SIGUSR2 = 12
SIGCLD = 17
SIGCHLD = 17
SIGPWR = 30
SIGIO = 29
SIGURG = 23
SIGWINCH = 28
SIGPOLL = 29
SIGSTOP = 19
SIGTSTP = 20
SIGCONT = 18
SIGTTIN = 21
SIGTTOU = 22
SIGVTALRM = 26
SIGPROF = 27
SIGXCPU = 24
SIGXFSZ = 25
SIGRTMIN, SIGRTMAX = _signals("rt")              # the C library's, read when the module is made (signal_add_constants)
SIGSTKFLT = 16
ITIMER_REAL = 0
ITIMER_VIRTUAL = 1
ITIMER_PROF = 2
SIG_DFL = 0                                      # PyLong_FromVoidPtr((void *)SIG_DFL): exact ints
SIG_IGN = 1


class ItimerError(OSError):                      # PyErr_NewException("signal.ItimerError", PyExc_OSError, NULL)
    pass


ItimerError.__module__ = "signal"
struct_siginfo = _structseq("struct_siginfo", "signal", ["si_signo", "si_code", "si_errno", "si_pid", "si_uid", "si_status", "si_band"], 7)

_ABSENT = object()
_EINTR = 4
_EAGAIN = 11
_EINVAL = 22
_PYTIME_MAX = 9223372036854775807


# ---- arguments

def _noargs(name: str, args: tuple[object, ...], kwds: dict[str, object]) -> None:   # METH_NOARGS
    if kwds:
        raise TypeError("_signal." + name + "() takes no keyword arguments")
    if args:
        raise TypeError("_signal." + name + "() takes no arguments (" + str(len(args)) + " given)")


def _one(name: str, args: tuple[object, ...], kwds: dict[str, object]) -> object:   # METH_O
    if kwds:
        raise TypeError("_signal." + name + "() takes no keyword arguments")
    if len(args) != 1:
        raise TypeError("_signal." + name + "() takes exactly one argument (" + str(len(args)) + " given)")
    return args[0]


def _positional(name: str, args: tuple[object, ...], kwds: dict[str, object], count: int) -> None:   # METH_FASTCALL, _PyArg_CheckPositional
    if kwds:
        raise TypeError("_signal." + name + "() takes no keyword arguments")
    if len(args) != count:
        raise TypeError(name + " expected " + str(count) + " argument" + ("" if count == 1 else "s") + ", got " + str(len(args)))


def _between(name: str, args: tuple[object, ...], kwds: dict[str, object], low: int, high: int) -> None:   # _PyArg_CheckPositional with a range
    if kwds:
        raise TypeError("_signal." + name + "() takes no keyword arguments")
    if len(args) < low:
        raise TypeError(name + " expected at least " + str(low) + " argument" + ("" if low == 1 else "s") + ", got " + str(len(args)))
    if len(args) > high:
        raise TypeError(name + " expected at most " + str(high) + " argument" + ("" if high == 1 else "s") + ", got " + str(len(args)))


def _type_lookup(value: object, name: str) -> object:   # _PyType_Lookup on its type: _ABSENT when it has none
    for klass in type(value).__mro__:
        found = vars(klass)
        if name in found:
            return found[name]
    return _ABSENT


def _int(value: object) -> int:                  # PyLong_AsInt
    out = _number_index(value)
    if not -2147483648 <= out <= 2147483647:
        raise OverflowError("Python int too large to convert to C int")
    return out


def _signum(value: object) -> int:               # a signal's number, as signal, getsignal, strsignal and siginterrupt take it
    signalnum = _int(value)
    if signalnum < 1 or signalnum >= NSIG:
        raise ValueError("signal number out of range")
    return signalnum


def _fail(code: int) -> None:                    # PyErr_SetFromErrno(PyExc_OSError)
    if code == _EINTR:
        _signals("check")                        # errors.c: a handler's exception stands where the InterruptedError would
    raise OSError(code, _signals("strerror", code))


def _fail_itimer(code: int) -> None:             # PyErr_SetFromErrno(modstate->itimer_error): the class is not errno's
    if code == _EINTR:
        _signals("check")
    raise ItimerError(code, _signals("strerror", code))


def _seconds_to_ns(value: object) -> int:        # _PyTime_FromSecondsObject(&t, obj, _PyTime_ROUND_CEILING)
    if _type_lookup(value, "__index__") is not _ABSENT:   # PyIndex_Check: PyLong_AsLongLong, then seconds to nanoseconds
        sec = _number_index(value)
        if not -(2**63) <= sec < 2**63 or not -(2**63) <= sec * 1000000000 < 2**63:
            raise OverflowError("timestamp out of range for C PyTime_t")
        return sec * 1000000000
    d = _as_double(value)
    if d != d:
        raise ValueError("Invalid value NaN (not a number)")
    d = d * 1e9                                  # pytime_from_double: ceil, and what a PyTime_t cannot hold (an infinity too)
    if not -9223372036854775808.0 <= d < 9223372036854775808.0:
        raise OverflowError("timestamp out of range for C PyTime_t")
    return d.__ceil__()


def _timeval(value: object) -> tuple[int, int]:  # timeval_from_double: _PyTime_AsTimeval(t, tv, _PyTime_ROUND_CEILING)
    ns = _seconds_to_ns(value)
    us = -((-ns) // 1000)                        # pytime_divide: up for t >= 0, C's own division (towards zero) below it
    return divmod(us, 1000000)                   # pytime_divmod: 0 <= tv_usec < 1000000


def _itimer_retval(old: tuple[int, int, int, int]) -> tuple[float, float]:   # itimer_retval: double_from_timeval twice
    return (old[0] + old[1] / 1000000.0, old[2] + old[3] / 1000000.0)


def _sigset(signals: object) -> tuple[int, ...]:   # _Py_Sigset_Converter: the numbers of an iterable, 1 to 64
    out: list[int] = []
    for item in signals:  # type: ignore[attr-defined]
        number = _number_index(item)
        if not -(2**63) <= number < 2**63:       # PyLong_AsLongAndOverflow: -1 and the overflow said
            number = -1
        if number <= 0 or number >= NSIG:
            raise ValueError("signal number " + str(number) + " out of range [1; " + str(NSIG - 1) + "]")
        error = _signals("sigaddset", number)
        if error == 0:
            out.append(number)
        elif error != _EINVAL:                   # "Probably impossible"
            _fail(error)
        else:                                    # one the C library keeps for itself: allowed, with a warning
            _warn("invalid signal number " + str(number) + ", please use valid_signals()", "RuntimeWarning")
    return tuple(out)


def _set_of(numbers: list[int]) -> set[int]:     # sigset_to_set: PySet_New(0), then each member in order
    out: set[int] = set()
    for number in numbers:
        out.add(number)
    return out


def _siginfo(fields: tuple[int, ...]) -> object:   # fill_siginfo; _PyLong_FromUid reads the all-ones id as -1
    return struct_siginfo((fields[0], fields[1], fields[2], fields[3], -1 if fields[4] == 4294967295 else fields[4], fields[5], fields[6]))


# ---- the functions, in signal_methods[]'s order

def default_int_handler(*args: object, **kwds: object) -> None:   # signal_default_int_handler_impl
    _positional("default_int_handler", args, kwds, 2)
    _int(args[0])
    raise KeyboardInterrupt


def alarm(*args: object, **kwds: object) -> int:   # signal_alarm_impl: (long)alarm(seconds), the int read as unsigned
    return _signals("alarm", _int(_one("alarm", args, kwds)))  # type: ignore[no-any-return]


def setitimer(*args: object, **kwds: object) -> tuple[float, float]:   # signal_setitimer_impl
    _between("setitimer", args, kwds, 2, 3)
    which = _int(args[0])
    seconds = _timeval(args[1])
    interval = _timeval(args[2]) if len(args) > 2 else (0, 0)   # NULL when absent; None is no number
    old = _signals("setitimer", which, seconds[0], seconds[1], interval[0], interval[1])   # "Let OS check "which" value"
    if type(old) is int:
        _fail_itimer(-old)
    return _itimer_retval(old)


def getitimer(*args: object, **kwds: object) -> tuple[float, float]:   # signal_getitimer_impl
    old = _signals("getitimer", _int(_one("getitimer", args, kwds)))
    if type(old) is int:
        _fail_itimer(-old)
    return _itimer_retval(old)


def signal(*args: object, **kwds: object) -> object:   # signal_signal_impl
    _positional("signal", args, kwds, 2)
    signalnum = _signum(args[0])
    handler = args[1]
    if callable(handler):                        # PyCallable_Check first: the runtime's C handler
        how = 2
    elif type(handler) is int and handler == 1:  # compare_handler: an exact int equal to SIG_IGN
        how = 1
    elif type(handler) is int and handler == 0:
        how = 0
    else:
        raise TypeError("signal handler must be signal.SIG_IGN, signal.SIG_DFL, or a callable object")
    _signals("check")                            # "Check for pending signals before changing signal handler"
    old = _signals("signal", signalnum, how, handler)
    if type(old) is int:
        _fail(-old)
    _signals("look")                             # the call is over: _CHECK_PERIODIC_AT_END, here and below
    return old[0]


def raise_signal(*args: object, **kwds: object) -> None:   # signal_raise_signal_impl: raise(), which refuses what it refuses
    code = _signals("raise", _int(_one("raise_signal", args, kwds)))
    if code < 0:
        _fail(-code)
    _signals("check")
    _signals("look")                             # what a handler that is not a Python function leaves queued is reported here


def strsignal(*args: object, **kwds: object) -> object:   # signal_strsignal_impl
    return _signals("strsignal", _signum(_one("strsignal", args, kwds)))


def getsignal(*args: object, **kwds: object) -> object:   # signal_getsignal_impl
    return _signals("handler", _signum(_one("getsignal", args, kwds)))


def set_wakeup_fd(*args: object, **kwds: object) -> int:   # signal_set_wakeup_fd_impl
    fdobj, warn = _unpack_keywords("set_wakeup_fd", ("", "warn_on_full_buffer"), 1, 1, 1, 0, args, kwds, _ABSENT)
    warn_on_full_buffer = True if warn is _ABSENT else bool(warn)   # PyObject_IsTrue in the wrapper: before the descriptor is read
    fd = _int(fdobj)
    if fd != -1:
        code = _signals("fstat", fd)             # _Py_fstat
        if code < 0:
            _fail(-code)
        blocking = _signals("blocking", fd)      # _Py_get_blocking
        if blocking < 0:
            _fail(-blocking)
        if blocking:
            raise ValueError("the fd " + str(fd) + " must be in non-blocking mode")
    return _signals("wakeup", fd, warn_on_full_buffer)  # type: ignore[no-any-return]


def siginterrupt(*args: object, **kwds: object) -> None:   # signal_siginterrupt_impl: both ints are read before the range is
    _positional("siginterrupt", args, kwds, 2)
    signalnum = _int(args[0])
    flag = _int(args[1])
    if signalnum < 1 or signalnum >= NSIG:
        raise ValueError("signal number out of range")
    code = _signals("siginterrupt", signalnum, flag)
    if code < 0:
        _fail(-code)


def pause(*args: object, **kwds: object) -> None:   # signal_pause_impl
    _noargs("pause", args, kwds)
    _signals("look_lean")                        # a lean build's look before the wait (CPython has none: D-24)
    _signals("pause")
    _signals("check")                            # "make sure that any exceptions that got raised are propagated back into Python"
    _signals("look")


def pidfd_send_signal(*args: object, **kwds: object) -> None:   # signal_pidfd_send_signal_impl
    _between("pidfd_send_signal", args, kwds, 2, 4)
    pidfd = _int(args[0])
    signalnum = _int(args[1])
    siginfo = args[2] if len(args) > 2 else None
    flags = _int(args[3]) if len(args) > 3 else 0
    if siginfo is not None:
        raise TypeError("siginfo must be None")
    code = _signals("pidfd_send_signal", pidfd, signalnum, flags)
    if code < 0:
        _fail(-code)
    _signals("look")                             # no PyErr_CheckSignals in the C: a signal to the process itself is handled when the call is over


def pthread_kill(*args: object, **kwds: object) -> None:   # signal_pthread_kill_impl
    _positional("pthread_kill", args, kwds, 2)
    if _type_lookup(args[0], "__index__") is _ABSENT:   # PyIndex_Check, _PyArg_BadArgument
        raise TypeError("pthread_kill() argument 1 must be int, not " + ("None" if args[0] is None else _tp_name(args[0])[:50]))
    thread_id = _number_index(args[0])           # unsigned_long(bitwise=True): 64 bits, with a warning for an int that has more
    if not -(2**63) <= thread_id < 2**64:
        _warn("integer value out of range", "DeprecationWarning")
    thread_id &= 0xFFFFFFFFFFFFFFFF
    signalnum = _int(args[1])
    # PySys_Audit("signal.pthread_kill", "ki", thread_id, signalnum): sys.audit looks at nothing yet
    code = _signals("pthread_kill", thread_id - 2**64 if thread_id >= 2**63 else thread_id, signalnum)   # the 64 bits, as a C long
    if code < 0:
        _fail(-code)
    _signals("check")                            # "the signal may have been send to the current thread"
    _signals("look")


def pthread_sigmask(*args: object, **kwds: object) -> set[int]:   # signal_pthread_sigmask_impl
    _positional("pthread_sigmask", args, kwds, 2)
    how = _int(args[0])
    mask = _sigset(args[1])
    previous = _signals("sigmask", how, mask)
    if type(previous) is int:
        _fail(-previous)
    _signals("check")                            # "if signals was unblocked, signal handlers have been called"
    _signals("look")
    return _set_of(previous)


def sigpending(*args: object, **kwds: object) -> set[int]:   # signal_sigpending_impl
    _noargs("sigpending", args, kwds)
    pending = _signals("sigpending")
    if type(pending) is int:
        _fail(-pending)
    return _set_of(pending)


def sigwait(*args: object, **kwds: object) -> int:   # signal_sigwait_impl: no PyErr_CheckSignals, and the C library waits on
    sigset = _sigset(_one("sigwait", args, kwds))
    _signals("look_lean")                        # a lean build's look before the wait (CPython has none: D-24)
    signum = _signals("sigwait", sigset)
    if signum < 0:
        _fail(-signum)
    _signals("look")                             # a handler whose signal came meanwhile runs when the call is over
    return signum  # type: ignore[no-any-return]


def sigwaitinfo(*args: object, **kwds: object) -> object:   # signal_sigwaitinfo_impl
    sigset = _sigset(_one("sigwaitinfo", args, kwds))
    _signals("look_lean")
    while True:
        result = _signals("sigwaitinfo", sigset)
        if type(result) is not int:
            break
        if result != -_EINTR:
            _fail(-result)
        _signals("check")                        # err == -1 && errno == EINTR && !(async_err = PyErr_CheckSignals())
    info = _siginfo(result)
    _signals("look")
    return info


def sigtimedwait(*args: object, **kwds: object) -> object:   # signal_sigtimedwait_impl
    _positional("sigtimedwait", args, kwds, 2)
    sigset = _sigset(args[0])
    timeout = _seconds_to_ns(args[1])
    if timeout < 0:
        raise ValueError("timeout must be non-negative")
    _signals("look_lean")                        # a lean build's, before the wait and before its deadline is taken (D-24)
    deadline = _signals("monotonic") + timeout   # _PyDeadline_Init: _PyTime_Add stops at PyTime_MAX
    if deadline > _PYTIME_MAX:
        deadline = _PYTIME_MAX
    info: object = None
    while True:
        result = _signals("sigtimedwait", sigset, timeout // 1000000000, timeout % 1000000000)   # _PyTime_AsTimespec
        if type(result) is not int:
            info = _siginfo(result)
            break
        if result == -_EAGAIN:                   # the time is over
            break
        if result != -_EINTR:
            _fail(-result)
        _signals("check")                        # "sigtimedwait() was interrupted by a signal (EINTR)"
        timeout = deadline - _signals("monotonic")   # _PyDeadline_Get
        if timeout < 0:                          # the handlers outlasted the time: None, where CPython 3.15.2 returns a
            break                                # struct_siginfo of a siginfo_t nothing wrote (docs/deviations.toml)
    _signals("look")
    return info


def valid_signals(*args: object, **kwds: object) -> set[int]:   # signal_valid_signals_impl: sigemptyset, sigfillset
    _noargs("valid_signals", args, kwds)
    valid = _signals("sigfillset")
    if type(valid) is int:
        _fail(-valid)
    return _set_of(valid)


# signal_module_exec's last step, signal_get_set_handlers: the table from what the program was started with (SIG_DFL, SIG_IGN,
# None for a handler that is not Python's), and KeyboardInterrupt for SIGINT if nobody had it ignored
_signals("exec", default_int_handler)
