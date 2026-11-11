# clause: C-7-70
# spec: section 7
# status: P1
# source: dialect specification section 7 (os), Modules/posixmodule.c (os_timerfd_create_impl, os_timerfd_settime_impl, os_timerfd_settime_ns_impl, os_timerfd_gettime_impl, os_timerfd_gettime_ns_impl, build_itimerspec, os_sched_param_impl, convert_sched_param, os_sched_get_priority_max_impl, os_sched_getscheduler_impl, os_sched_setscheduler_impl, os_sched_getparam_impl, os_sched_setparam_impl, os_sched_rr_get_interval_impl, os_sched_setaffinity_impl, os_sched_getaffinity_impl, os_ctermid_impl, os_device_encoding_impl, os_pidfd_open_impl), Python/pytime.c (pytime_from_double)
"""Timers that are descriptors (timerfd_create, the two settimes and the two gettimes, in seconds and in nanoseconds) and how the
process is scheduled: sched_param, the policy and its priorities, the CPUs the process may run on; with them pidfd_open, ctermid
and device_encoding. What each returns, what it refuses, and what its OSError carries (none of them a file name)."""
# ruff: noqa: E501, PTH
# The machine's own numbers (which CPUs, the round-robin quantum, how long is left on a timer) are printed as kinds and relations;
# a timer that is only looked at is set minutes ahead, so that a machine that stalls for a second answers the same.
import copy
import os
import tempfile
import time
from collections.abc import Callable


def m(f: Callable[[], object]) -> str:
    try:
        return repr(f())
    except OSError as e:
        return type(e).__name__ + ": " + repr((e.errno, e.strerror, e.filename))
    except Exception as e:
        return type(e).__name__


class Index:
    def __init__(self, value: int) -> None:
        self.value = value

    def __index__(self) -> int:
        return self.value


class Float:
    def __float__(self) -> float:
        return 2.5


class Fileno:
    def __init__(self, fd: int) -> None:
        self.fd = fd

    def fileno(self) -> int:
        return self.fd


def expirations(fd: int) -> int:
    return int.from_bytes(os.read(fd, 8), "little")


def main() -> None:
    d = tempfile.mkdtemp()
    name = os.path.join(d, "f")
    with open(name, "wb") as f:
        f.write(b"x")
    plain = os.open(name, os.O_RDONLY)

    # a timer: not inheritable, blocking unless asked; what is left of it, in seconds and in nanoseconds
    t = os.timerfd_create(time.CLOCK_MONOTONIC)
    print("timerfd_create:", t > 2, os.get_inheritable(t), os.get_blocking(t), os.timerfd_gettime(t), os.timerfd_gettime_ns(t), os.timerfd_settime(t, initial=1000.5, interval=2.25), [type(v).__name__ for v in os.timerfd_gettime(t)],
          os.timerfd_gettime(t)[1], 900 < os.timerfd_gettime(t)[0] <= 1000.5, os.timerfd_gettime_ns(t)[1], 900 * 10**9 < os.timerfd_gettime_ns(Fileno(t))[0] <= 1000500000000)  # type: ignore[arg-type]
    old = os.timerfd_settime_ns(t, initial=500 * 10**9, interval=7)
    print("in nanoseconds:", type(old).__name__, [type(v).__name__ for v in old], old[1], 900 * 10**9 < old[0] <= 1000500000000, os.timerfd_gettime_ns(t)[1], os.timerfd_gettime(t)[1], 400 < os.timerfd_settime(t)[0] <= 500, os.timerfd_gettime(t),
          os.timerfd_gettime_ns(t))
    print("what a time may be:", os.timerfd_settime(t, initial=Float(), interval=Index(3)), os.timerfd_gettime(t)[1], os.timerfd_settime(t, initial=1, interval=True)[1], os.timerfd_gettime_ns(t)[1],  # type: ignore[arg-type]
          os.timerfd_settime(t, flags=0, initial=0.0000000019)[1], os.timerfd_settime_ns(t, initial=Index(400 * 10**9))[0] in (0, 1), 300 * 10**9 < os.timerfd_gettime_ns(t)[0] <= 400 * 10**9, os.timerfd_settime_ns(t, initial=2**63 - 1)[1],  # type: ignore[arg-type]
          os.timerfd_settime(t, flags=os.TFD_TIMER_ABSTIME, initial=time.monotonic() + 500)[1], 400 < os.timerfd_gettime(t)[0] <= 500, os.timerfd_settime(t)[1], (os.TFD_CLOEXEC, os.TFD_NONBLOCK, os.TFD_TIMER_ABSTIME))

    # it is read: how many times it has gone off since the last read
    n = os.timerfd_create(time.CLOCK_REALTIME, flags=os.TFD_NONBLOCK)
    os.timerfd_settime(t, initial=0.02)
    once = expirations(t)
    os.timerfd_settime_ns(t, initial=1, interval=10**7)
    time.sleep(0.06)
    print("reading:", os.get_blocking(n), os.get_inheritable(n), m(lambda: os.read(n, 8)), once, os.timerfd_gettime(t)[1], expirations(t) >= 3, os.timerfd_settime(t)[1], os.timerfd_gettime_ns(t))
    print("timerfd refuses:", m(lambda: os.timerfd_create()), m(lambda: os.timerfd_create(99)), m(lambda: os.timerfd_create("x")), m(lambda: os.timerfd_create(1, 0)), m(lambda: os.timerfd_create(1, flags=12345)),  # type: ignore[arg-type, call-arg]
          m(lambda: os.timerfd_create(clockid=1)), m(lambda: os.timerfd_create(2**40)), m(lambda: os.timerfd_create(1.5)), m(lambda: os.timerfd_settime()), m(lambda: os.timerfd_settime(987)), m(lambda: os.timerfd_settime("x")),  # type: ignore[call-arg, arg-type]
          m(lambda: os.timerfd_settime(t, 0)), m(lambda: os.timerfd_settime(t, initial="x")), m(lambda: os.timerfd_settime(t, initial=-1)), m(lambda: os.timerfd_settime(t, interval=-0.5)), m(lambda: os.timerfd_settime(t, initial=float("nan"))),  # type: ignore[arg-type, call-arg]
          m(lambda: os.timerfd_settime(t, initial=float("inf"))), m(lambda: os.timerfd_settime(t, initial=9.3e9)), m(lambda: os.timerfd_settime(t, initial=-1e-10)), m(lambda: os.timerfd_settime(t, flags=99)), m(lambda: os.timerfd_settime(plain, initial=1)),
          m(lambda: os.timerfd_settime(fd=t)), m(lambda: os.timerfd_settime(t, initial=None)), m(lambda: os.timerfd_settime_ns(t, initial=1.5)), m(lambda: os.timerfd_settime_ns(t, initial=-1)), m(lambda: os.timerfd_settime_ns(t, interval=-1)),  # type: ignore[call-arg, arg-type]
          m(lambda: os.timerfd_settime_ns(t, initial=2**63)), m(lambda: os.timerfd_settime_ns(t, 0)), m(lambda: os.timerfd_settime_ns(987)), m(lambda: os.timerfd_settime_ns(plain, initial=1)), m(lambda: os.timerfd_gettime()),  # type: ignore[call-arg]
          m(lambda: os.timerfd_gettime(987)), m(lambda: os.timerfd_gettime("x")), m(lambda: os.timerfd_gettime(plain)), m(lambda: os.timerfd_gettime(t, 1)), m(lambda: os.timerfd_gettime(fd=t)), m(lambda: os.timerfd_gettime_ns(987)),  # type: ignore[arg-type, call-arg]
          m(lambda: os.timerfd_gettime_ns(1.5)), m(lambda: os.timerfd_gettime_ns(plain)), os.timerfd_gettime(t))  # type: ignore[arg-type]

    # sched_param: one field, whatever is given; it is asked for an int only when it is used
    P = os.sched_param  # noqa: N806
    p = P(5)
    print("sched_param:", P.__name__, P.__module__, P.__mro__ == (P, tuple, object), P.n_fields, P.n_sequence_fields, P.n_unnamed_fields, P.__match_args__, p, p.sched_priority, len(p), p[0], tuple(p), p == (5,), hash(p) == hash((5,)),
          p.__reduce__() == (P, (5,)), P(sched_priority=3), P("x"), P((1,)), copy.copy(p), copy.replace(p, sched_priority=7), type(P.sched_priority).__name__, m(lambda: P()), m(lambda: P(1, 2)), m(lambda: P(x=1)),  # type: ignore[call-arg, arg-type]
          m(lambda: type("S", (P,), {})), m(lambda: setattr(p, "sched_priority", 1)), m(lambda: p.x))  # type: ignore[attr-defined]

    # the policy and its priorities
    print("priorities:", [(os.sched_get_priority_min(policy), os.sched_get_priority_max(policy)) for policy in (os.SCHED_OTHER, os.SCHED_FIFO, os.SCHED_RR, os.SCHED_BATCH, os.SCHED_IDLE)], os.sched_get_priority_max(policy=os.SCHED_RR),
          os.sched_get_priority_min(Index(os.SCHED_FIFO)), m(lambda: os.sched_get_priority_max(99)), m(lambda: os.sched_get_priority_min(-1)), m(lambda: os.sched_get_priority_max("x")), m(lambda: os.sched_get_priority_max()),  # type: ignore[arg-type, call-arg]
          m(lambda: os.sched_get_priority_max(2**40)), m(lambda: os.sched_get_priority_min(1.5)), m(lambda: os.sched_get_priority_max(1, 2)), (os.SCHED_OTHER, os.SCHED_FIFO, os.SCHED_RR, os.SCHED_BATCH, os.SCHED_IDLE, os.SCHED_RESET_ON_FORK))  # type: ignore[arg-type, call-arg]
    me = os.getpid()
    print("the scheduler:", os.sched_getscheduler(0) == os.sched_getscheduler(me), os.sched_getscheduler(0) in (os.SCHED_OTHER, os.SCHED_BATCH, os.SCHED_IDLE), os.sched_getparam(0), type(os.sched_getparam(me)) is P, os.sched_setparam(0, P(0)), os.sched_setscheduler(0, os.SCHED_BATCH, P(0)), os.sched_getscheduler(0),  # type: ignore[func-returns-value]
          os.sched_setscheduler(me, os.SCHED_OTHER, P(Index(0))), os.sched_getscheduler(0), type(os.sched_rr_get_interval(0)).__name__, os.sched_rr_get_interval(me) >= 0)  # type: ignore[arg-type, func-returns-value]
    print("the scheduler refuses:", m(lambda: os.sched_getscheduler(2**30)), m(lambda: os.sched_getscheduler(-1)), m(lambda: os.sched_getscheduler("x")), m(lambda: os.sched_getscheduler()), m(lambda: os.sched_getscheduler(pid=0)),  # type: ignore[arg-type, call-arg]
          m(lambda: os.sched_getscheduler(2**70)), m(lambda: os.sched_getparam(2**30)), m(lambda: os.sched_getparam(-1)), m(lambda: os.sched_getparam()), m(lambda: os.sched_setparam(0, P(5))), m(lambda: os.sched_setparam(0, (0,))),  # type: ignore[call-arg, arg-type]
          m(lambda: os.sched_setparam(0, P("x"))), m(lambda: os.sched_setparam(0, P(2**40))), m(lambda: os.sched_setparam(0, P(2**70))), m(lambda: os.sched_setparam(0, P(1.5))), m(lambda: os.sched_setparam(2**30, P(0))), m(lambda: os.sched_setparam("x", 0)),  # type: ignore[arg-type]
          m(lambda: os.sched_setparam(0)), m(lambda: os.sched_setparam(pid=0, param=P(0))), m(lambda: os.sched_setparam(0, P(-1))), m(lambda: os.sched_setscheduler(0, os.SCHED_OTHER, P(3))), m(lambda: os.sched_setscheduler(0, 99, P(0))),  # type: ignore[call-arg]
          m(lambda: os.sched_setscheduler(0, os.SCHED_OTHER, 0)), m(lambda: os.sched_setscheduler(0, "x", P(0))), m(lambda: os.sched_setscheduler("x", 0, 0)), m(lambda: os.sched_setscheduler(0, 0)), m(lambda: os.sched_setscheduler(2**30, 0, P(0))),  # type: ignore[arg-type, call-arg]
          m(lambda: os.sched_setscheduler(0, 2**40, 5)), m(lambda: os.sched_rr_get_interval(2**30)), m(lambda: os.sched_rr_get_interval(-1)), m(lambda: os.sched_rr_get_interval("x")), m(lambda: os.sched_rr_get_interval()), os.sched_getscheduler(0))  # type: ignore[arg-type, call-arg]

    # the CPUs the process may run on: a set, taken from anything that gives ints
    allowed = os.sched_getaffinity(0)
    one = min(allowed)
    print("affinity:", type(allowed).__name__, len(allowed) >= 1, all(type(cpu) is int for cpu in allowed), allowed == os.sched_getaffinity(me), os.process_cpu_count() == len(allowed), (os.cpu_count() or 0) >= len(allowed),
          os.sched_setaffinity(0, [one]), os.sched_getaffinity(0) == {one}, os.sched_setaffinity(me, iter(allowed)), os.sched_getaffinity(0) == allowed, os.sched_setaffinity(0, (Index(one), one, 100000)), os.sched_getaffinity(0) == {one},  # type: ignore[func-returns-value, arg-type]
          os.sched_setaffinity(0, allowed), os.sched_getaffinity(0) == allowed)  # type: ignore[func-returns-value]
    print("affinity refuses:", m(lambda: os.sched_setaffinity(0, [])), m(lambda: os.sched_setaffinity(0, 5)), m(lambda: os.sched_setaffinity(0, ["x"])), m(lambda: os.sched_setaffinity(0, [-1])), m(lambda: os.sched_setaffinity(0, [2**31 - 1])),  # type: ignore[arg-type, list-item]
          m(lambda: os.sched_setaffinity(0, [2**70])), m(lambda: os.sched_setaffinity(0, [1.5])), m(lambda: os.sched_setaffinity(0, [100000])), m(lambda: os.sched_setaffinity(2**30, allowed)), m(lambda: os.sched_setaffinity(0)),  # type: ignore[list-item, call-arg]
          m(lambda: os.sched_setaffinity(0, allowed, 1)), m(lambda: os.sched_setaffinity(0, "0")), m(lambda: os.sched_setaffinity(0, [one, "x"])), m(lambda: os.sched_setaffinity("x", allowed)), m(lambda: os.sched_getaffinity(2**30)),  # type: ignore[call-arg, list-item, arg-type]
          m(lambda: os.sched_getaffinity(-1)), m(lambda: os.sched_getaffinity("x")), m(lambda: os.sched_getaffinity()), m(lambda: os.sched_getaffinity(pid=0)), os.sched_getaffinity(0) == allowed)  # type: ignore[arg-type, call-arg]

    # a descriptor for a process, the terminal's name, and the encoding of a descriptor that is no terminal
    pidfd = os.pidfd_open(me)
    print("pidfd_open:", pidfd > 2, os.get_inheritable(pidfd), os.pidfd_open(pid=me, flags=0) > 2, m(lambda: os.pidfd_open(2**30)), m(lambda: os.pidfd_open(-1)), m(lambda: os.pidfd_open(0)), m(lambda: os.pidfd_open()), m(lambda: os.pidfd_open("x")),  # type: ignore[call-arg, arg-type]
          m(lambda: os.pidfd_open(me, 12345)), m(lambda: os.pidfd_open(me, -1)), m(lambda: os.pidfd_open(me, 2**32)), m(lambda: os.pidfd_open(me, 0, 0)), m(lambda: os.pidfd_open(me, "0")))  # type: ignore[call-arg, arg-type]
    print("ctermid and device_encoding:", os.ctermid(), m(lambda: os.ctermid(1)), os.device_encoding(plain), os.device_encoding(987), os.device_encoding(t), os.device_encoding(fd=plain), os.device_encoding(-1), os.device_encoding(Index(plain)),  # type: ignore[call-arg, arg-type]
          m(lambda: os.device_encoding("x")), m(lambda: os.device_encoding()), m(lambda: os.device_encoding(1.5)), m(lambda: os.device_encoding(2**40)), m(lambda: os.device_encoding(plain, 1)))  # type: ignore[arg-type, call-arg]

    for descriptor in (plain, t, n, pidfd):
        os.close(descriptor)
    os.unlink(name)
    os.rmdir(d)


if __name__ == "__main__":
    main()
