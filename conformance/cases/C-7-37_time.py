# clause: C-7-37
# spec: section 7
# status: P1
# source: dialect specification section 7, Modules/timemodule.c, Python/pytime.c
"""time: the clocks' types and conventions, gmtime and localtime with every conversion message, mktime, strftime through the C library
with Python's checks and the split at non-ASCII characters, asctime and ctime, struct_time, the CLOCK_* constants, get_clock_info,
sleep's conversions, and tzset with the January-and-July rule for timezone, altzone, daylight and tzname. What a clock reads is
compared by type and bound only."""
# ruff: noqa: ANN001, ANN002, ANN003, ANN201, ANN202, ANN204, B018, B023, E501, E731, E741, E742, F601, PLR0133, SLF001
import _thread
import os
import time

os.environ["TZ"] = "CET-1CEST,M3.5.0,M10.5.0/3"   # the recording's zone as a POSIX rule: no host setting, no zone database
time.tzset()


def m(f):  # type: ignore[no-untyped-def]
    try:
        return repr(f())
    except Exception as e:
        return type(e).__name__ + ": " + str(e)


print(time.CLOCK_REALTIME, time.CLOCK_MONOTONIC, time.CLOCK_PROCESS_CPUTIME_ID, time.CLOCK_THREAD_CPUTIME_ID, time.CLOCK_MONOTONIC_RAW, time.CLOCK_BOOTTIME, time._STRUCT_TM_ITEMS)  # type: ignore[attr-defined]
print(time.timezone, time.altzone, time.daylight, time.tzname)
st = time.struct_time
print(st.__mro__[1:], st.n_sequence_fields, st.n_fields, st.n_unnamed_fields, st.__module__, st.__name__)
g = time.gmtime(0)
print(g, g.tm_zone, g.tm_gmtoff, len(g), tuple(g), g[8], type(g.tm_year))
print(time.gmtime(1700000000), time.gmtime(-1), time.gmtime(86399.999), time.gmtime(True), type(time.gmtime(None)), time.gmtime(2**40), time.gmtime(-2**40))
print(time.localtime(0), time.localtime(0).tm_zone, time.localtime(0).tm_gmtoff, time.localtime(1700000000), time.localtime(1690000000).tm_isdst, time.localtime(1690000000).tm_zone)
print(m(lambda: time.gmtime(2**70)), m(lambda: time.gmtime(float("nan"))), m(lambda: time.gmtime(float("inf"))), m(lambda: time.gmtime(1e30)), m(lambda: time.gmtime("1")), m(lambda: time.gmtime(1, 2)), m(lambda: time.gmtime(secs=1)), m(lambda: time.gmtime(2**62)), m(lambda: time.localtime(2**62)), m(lambda: time.gmtime(-2**62)), m(lambda: time.gmtime(2**63 - 1)), m(lambda: time.gmtime(-2**63)))  # type: ignore[arg-type,call-arg,no-untyped-call]
print(time.mktime(time.localtime(1700000000)), time.mktime((2023, 11, 14, 23, 13, 20, 1, 318, -1)), time.mktime((2023, 11, 14, 23, 13, 20, 1, 318, 0)), time.mktime((2023, 11, 14, 23, 13, 20, 1, 318, 1)), time.mktime((2023, 13, 45, 25, 61, 61, 0, 0, -1)), time.mktime(time.gmtime(0)), time.mktime((1970, 1, 1, 0, 0, 0, 0, 0, 0)))
print(m(lambda: time.mktime((1, 2))), m(lambda: time.mktime([2023, 11, 14, 23, 13, 20, 1, 318, -1])), m(lambda: time.mktime((2023, 11, 14, 23, 13, 20, 1, 318, "x"))), m(lambda: time.mktime((2023.0, 11, 14, 23, 13, 20, 1, 318, 0))), m(lambda: time.mktime((2**40, 11, 14, 23, 13, 20, 1, 318, 0))), m(lambda: time.mktime((-2**31, 1, 1, 0, 0, 0, 0, 0, 0))), m(lambda: time.mktime((-2**31 + 1900, 1, 1, 0, 0, 0, 0, 0, 0))), m(lambda: time.mktime((2**30, 1, 1, 0, 0, 0, 0, 0, 0))), m(lambda: time.mktime()), m(lambda: time.mktime(1, 2)))  # type: ignore[arg-type,call-arg,no-untyped-call]
t0 = (2023, 11, 14, 23, 13, 20, 1, 318, 0)
for fmt in ("%Y-%m-%d %H:%M:%S", "%a %A %b %B %c", "%j %U %W %w %u %V %G %g", "%y %C %e %I %p %Z %z %%", "", "%", "%5", "é%Yé", "%Y\x00%m", "%Q %E", "a%", "%-d %_d %0d", "%s", "%n%t|", "%D %F %R %T %r %x %X %h %k %l %P"):
    print(repr(fmt), m(lambda: time.strftime(fmt, t0)))  # type: ignore[no-untyped-call]
print(time.strftime("%Y %Z %z", time.gmtime(0)), time.strftime("%Y %Z %z", time.localtime(0)), time.strftime("%Z|%z", (2023, 1, 1, 0, 0, 0, 0, 1, -1)), time.strftime("%Z|%z", (2023, 1, 1, 0, 0, 0, 0, 1, 1)), time.strftime("%Z|%z", (2023, 1, 1, 0, 0, 0, 0, 1, 5)), time.strftime("%Z|%z", (2023, 1, 1, 0, 0, 0, 0, 1, -7)))
print(time.strftime("%Y", (1, 1, 1, 0, 0, 0, 0, 1, 0)), time.strftime("%Y %y", (-5, 1, 1, 0, 0, 0, 0, 1, 0)), time.strftime("%Y", (99999, 1, 1, 0, 0, 0, 0, 1, 0)), time.strftime("%d|%m|%j", (2023, 0, 0, 0, 0, 0, 0, 0, 0)), time.strftime("%S", (2023, 1, 1, 0, 0, 61, 0, 1, 0)), time.strftime("%a", (2023, 1, 1, 0, 0, 0, 6, 1, 0)), time.strftime("%a", (2023, 1, 1, 0, 0, 0, 13, 1, 0)))
for bad in ((2023, 13, 1, 0, 0, 0, 0, 1, 0), (2023, -1, 1, 0, 0, 0, 0, 1, 0), (2023, 1, 32, 0, 0, 0, 0, 1, 0), (2023, 1, -1, 0, 0, 0, 0, 1, 0), (2023, 1, 1, 24, 0, 0, 0, 1, 0), (2023, 1, 1, -1, 0, 0, 0, 1, 0), (2023, 1, 1, 0, 60, 0, 0, 1, 0), (2023, 1, 1, 0, 0, 62, 0, 1, 0), (2023, 1, 1, 0, 0, -1, 0, 1, 0), (2023, 1, 1, 0, 0, 0, -1, 1, 0), (2023, 1, 1, 0, 0, 0, 0, 367, 0), (2023, 1, 1, 0, 0, 0, 0, -1, 0), (2023, 1, 1, 0, 0, 0, 0, 1), (2023, 1, 1, 0, 0, 0, 0, 1, 0, 0), (2023, 1, 1, 0, 0, 0, 0, 1, 1.5), ("2023", 1, 1, 0, 0, 0, 0, 1, 0), (2**31, 1, 1, 0, 0, 0, 0, 1, 0), (-2**31, 1, 1, 0, 0, 0, 0, 1, 0), (2023, 1, 1, 0, 0, 0, 0, 1, 2**40), [2023, 1, 1, 0, 0, 0, 0, 1, 0]):
    print(bad, m(lambda: time.strftime("%Y", bad)), m(lambda: time.asctime(bad)))  # type: ignore[arg-type,no-untyped-call]
print(m(lambda: time.strftime(b"%Y")), m(lambda: time.strftime()), m(lambda: time.strftime("%Y", t0, 1)), m(lambda: time.strftime("%Y", t0, x=1)), m(lambda: time.strftime(format="%Y")))  # type: ignore[arg-type,call-arg,no-untyped-call]
print(time.asctime(t0), time.asctime(time.gmtime(0)), time.asctime((2023, 1, 1, 0, 0, 0, 0, 1, 0)), time.asctime((2023, 12, 31, 23, 59, 61, 6, 366, 1)), time.ctime(0), time.ctime(1700000000), time.ctime(-1), m(lambda: time.asctime(1, 2)), m(lambda: time.asctime(1)), m(lambda: time.ctime("x")), m(lambda: time.ctime(2**70)), type(time.ctime()), type(time.asctime()))  # type: ignore[arg-type,call-arg,no-untyped-call]
print(type(time.time()), type(time.time_ns()), type(time.monotonic()), type(time.monotonic_ns()), type(time.perf_counter()), type(time.perf_counter_ns()), type(time.process_time()), type(time.process_time_ns()), type(time.thread_time()), type(time.thread_time_ns()), time.time() > 1.7e9, time.time_ns() > 1.7e18, time.monotonic_ns() > 0, time.process_time() >= 0)
print(m(lambda: time.time(1)), m(lambda: time.time(x=1)), m(lambda: time.monotonic_ns(1)), m(lambda: time.sleep()), m(lambda: time.sleep(1, 2)), m(lambda: time.sleep(-1)), m(lambda: time.sleep(-0.0)), m(lambda: time.sleep("1")), m(lambda: time.sleep(float("nan"))), m(lambda: time.sleep(1e30)), m(lambda: time.sleep(2**70)), m(lambda: time.sleep(secs=1)), time.sleep(0), time.sleep(0.001), time.sleep(True))  # type: ignore[arg-type,call-arg,func-returns-value,no-untyped-call]
print(type(time.clock_gettime(time.CLOCK_REALTIME)), type(time.clock_gettime_ns(1)), time.clock_gettime(0) > 1.7e9, time.clock_gettime_ns(0) > 1.7e18, time.clock_getres(1), time.clock_getres(0), m(lambda: time.clock_gettime(99)), m(lambda: time.clock_gettime("1")), m(lambda: time.clock_gettime(1.5)), m(lambda: time.clock_gettime(2**40)), m(lambda: time.clock_gettime()), m(lambda: time.clock_gettime(1, 2)), m(lambda: time.clock_getres(99)), m(lambda: time.clock_getres("1")), m(lambda: time.clock_getres(1.5)), m(lambda: time.clock_getres(2**40)), m(lambda: time.clock_gettime_ns(clk_id=1)))  # type: ignore[arg-type,call-arg,no-untyped-call]
print(m(lambda: time.clock_settime(0, 1)), m(lambda: time.clock_settime(0, "1")), m(lambda: time.clock_settime("0", 1)), m(lambda: time.clock_settime(0, float("nan"))), m(lambda: time.clock_settime(0, 1e30)), m(lambda: time.clock_settime_ns(0, 1)), m(lambda: time.clock_settime_ns(0, 1.5)), m(lambda: time.clock_settime_ns(0, 2**70)), m(lambda: time.clock_settime(0)), m(lambda: time.clock_settime_ns(1, 2, 3)))  # type: ignore[arg-type,call-arg,no-untyped-call]
for name in ("time", "monotonic", "perf_counter", "process_time", "thread_time"):
    print(name, time.get_clock_info(name), type(time.get_clock_info(name)).__name__, type(time.get_clock_info(name)).__module__)
print(m(lambda: time.get_clock_info("clock")), m(lambda: time.get_clock_info(1)), m(lambda: time.get_clock_info("ti\x00me")), m(lambda: time.get_clock_info()), m(lambda: time.get_clock_info(name="time")))  # type: ignore[arg-type,call-arg,no-untyped-call]
print(type(time.pthread_getcpuclockid(_thread.get_ident())), m(lambda: time.pthread_getcpuclockid(1.5)), m(lambda: time.pthread_getcpuclockid("1")), m(lambda: time.pthread_getcpuclockid()))  # type: ignore[arg-type,call-arg,no-untyped-call]
print(time.struct_time((1, 2, 3, 4, 5, 6, 7, 8, 9)), time.struct_time((1, 2, 3, 4, 5, 6, 7, 8, 9)).tm_zone, time.struct_time((1, 2, 3, 4, 5, 6, 7, 8, 9, "Z", 5)).tm_gmtoff, m(lambda: time.struct_time((1, 2))), m(lambda: time.struct_time((1, 2, 3, 4, 5, 6, 7, 8, 9, "Z", 5, 6))), time.struct_time((1, 2, 3, 4, 5, 6, 7, 8, 9)) == (1, 2, 3, 4, 5, 6, 7, 8, 9), repr(time.gmtime(0)), m(lambda: time.strftime("%Y", time.struct_time((2000, 1, 1, 0, 0, 0, 0, 1, 0, b"x", 0)))), m(lambda: time.strftime("%Z", time.struct_time((2000, 1, 1, 0, 0, 0, 0, 1, 0, "A\x00B", 0)))), time.strftime("%Z %z", time.struct_time((2000, 1, 1, 0, 0, 0, 0, 1, 0, "XYZ", 3600))), time.mktime(time.struct_time((2000, 1, 1, 0, 0, 0, 0, 1, 0, "XYZ", 3600))))  # type: ignore[no-untyped-call]
os.environ["TZ"] = "UTC0"
time.tzset()
print(time.timezone, time.altzone, time.daylight, time.tzname, time.localtime(0), time.strftime("%Z %z", time.localtime(0)), time.mktime(time.gmtime(0)), m(lambda: time.tzset(1)))  # type: ignore[call-arg,no-untyped-call]
os.environ["TZ"] = "EST5EDT,M3.2.0,M11.1.0"
time.tzset()
print(time.timezone, time.altzone, time.daylight, time.tzname, time.localtime(1690000000), time.ctime(1690000000), time.mktime((2023, 7, 22, 0, 0, 0, 0, 0, -1)), time.mktime((2023, 7, 22, 0, 0, 0, 0, 0, 0)))
os.environ["TZ"] = "EST+5EDT,M3.2.0,M11.1.0"
time.tzset()
print(time.timezone, time.altzone, time.daylight, time.tzname, time.localtime(0))
