"""time, in Python (Modules/timemodule.c and Python/pytime.c) over posix.cpp's calls: the clocks and their float and nanosecond
forms, sleep, gmtime, localtime, mktime, strftime, asctime, ctime, strptime through _strptime, struct_time, tzset and the library's
timezone, altzone, daylight and tzname, get_clock_info, the CLOCK_* constants. Each conversion is the C's: a timestamp floors to a
time_t with its messages, a sleep rounds its nanoseconds up, a float of nanoseconds is exact where it can be."""

__all__ = ["CLOCK_BOOTTIME", "CLOCK_MONOTONIC", "CLOCK_MONOTONIC_RAW", "CLOCK_PROCESS_CPUTIME_ID", "CLOCK_REALTIME", "CLOCK_THREAD_CPUTIME_ID",
           "_STRUCT_TM_ITEMS", "altzone", "asctime", "clock_getres", "clock_gettime", "clock_gettime_ns", "clock_settime", "clock_settime_ns",
           "ctime", "daylight", "get_clock_info", "gmtime", "localtime", "mktime", "monotonic", "monotonic_ns", "perf_counter",
           "perf_counter_ns", "process_time", "process_time_ns", "pthread_getcpuclockid", "sleep", "strftime", "strptime", "struct_time",
           "thread_time", "thread_time_ns", "time", "time_ns", "timezone", "tzname", "tzset"]

__name__ = "time"

try:
    _bella_refuse                                # noqa: B018  # a facility phase 1 lacks, where it would run
    _bella_bootstrap                             # noqa: B018  # bootstrap.py's functions and classes by name (SimpleNamespace)
    _tp_name                                     # noqa: B018  # Py_TYPE(o)->tp_name
    _structseq                                   # noqa: B018  # bootstrap.py's: a type of named tuples
    _sys                                         # noqa: B018  # posix.cpp: one C library call by name
    _bella_module_set                            # noqa: B018  # PyModule_Add on the module itself, once imported (tzset)
    _number_index                                # noqa: B018  # PyNumber_Index
    _as_double                                   # noqa: B018  # PyFloat_AsDouble
except NameError:
    from collections.abc import Callable
    from typing import Any

    def _missing(*args: object) -> Any:
        raise ImportError("this file needs the runtime's primitives")

    _bella_refuse: Callable[..., Any] = _missing
    _bella_bootstrap: Callable[..., Any] = _missing
    _structseq: Callable[..., Any] = _missing
    _sys: Callable[..., Any] = _missing
    _bella_module_set: Callable[..., Any] = _missing

    def _tp_name(o: object) -> str:
        return type(o).__name__

    def _number_index(o: object) -> int:
        import operator
        return operator.index(o)

    def _as_double(value: object) -> float:   # PyFloat_AsDouble, for probing this file under CPython
        return float(value)  # type: ignore[arg-type]

CLOCK_REALTIME = 0
CLOCK_MONOTONIC = 1
CLOCK_PROCESS_CPUTIME_ID = 2
CLOCK_THREAD_CPUTIME_ID = 3
CLOCK_MONOTONIC_RAW = 4
CLOCK_BOOTTIME = 7
_STRUCT_TM_ITEMS = 11

_SEC_TO_NS = 1000000000
_INT_MAX = 2**31 - 1
_INT_MIN = -(2**31)
_TIME_T_MIN = -(2**63)
_TIME_T_MAX = 2**63 - 1

struct_time = _structseq("struct_time", "time", ["tm_year", "tm_mon", "tm_mday", "tm_hour", "tm_min", "tm_sec", "tm_wday", "tm_yday",
                                                 "tm_isdst", "tm_zone", "tm_gmtoff"], 9)
struct_time.__doc__ = ("The time value as returned by gmtime(), localtime(), and strptime(), and\n accepted by asctime(), mktime() and "
                       "strftime().  May be considered as a\n sequence of 9 integers.\n\n Note that several fields' values are not the same as "
                       "those defined by\n the C language standard for struct tm.  For example, the value of the\n field tm_year is the actual "
                       "year, not year - 1900.  See individual\n fields' descriptions for details.")


# ---- conversions (Python/pytime.c) --------------------------------------------------------------------------------------------

_index = _number_index                           # PyNumber_Index: the runtime's, with its messages (review G15 #6)


def _fail(code: int) -> None:                    # PyErr_SetFromErrno(OSError)
    raise OSError(code, _sys("strerror", code))


def _object_to_time_t(value: object) -> int:     # _PyTime_ObjectToTime_t with _PyTime_ROUND_FLOOR: an index, or else a real number
    if hasattr(type(value), "__index__"):
        try:
            n = _index(value)
        except OverflowError:
            raise OverflowError("timestamp out of range for platform time_t") from None
        if n < _TIME_T_MIN or n > _TIME_T_MAX:
            raise OverflowError("timestamp out of range for platform time_t")
        return n
    d = _as_double(value)
    if d != d:
        raise ValueError("Invalid value NaN (not a number)")
    if not (-9223372036854775808.0 <= d < 9223372036854775808.0):
        raise OverflowError("timestamp out of range for platform time_t")
    return int(d.__floor__())


def _seconds_to_ns(value: object, round_up: bool) -> int:   # _PyTime_FromSecondsObject: nanoseconds, floored or rounded towards +inf
    if hasattr(type(value), "__index__"):
        try:
            sec = _index(value)
        except OverflowError:
            raise OverflowError("timestamp out of range for C PyTime_t") from None
        if sec < -(2**63) or sec > 2**63 - 1 or not (-(2**63) <= sec * _SEC_TO_NS <= 2**63 - 1):
            raise OverflowError("timestamp out of range for C PyTime_t")
        return sec * _SEC_TO_NS
    d = _as_double(value)
    if d != d:
        raise ValueError("Invalid value NaN (not a number)")
    d = d * 1e9
    d = float(d.__ceil__() if round_up else d.__floor__()) if -9223372036854775808.0 < d < 9223372036854775808.0 else d
    if not (-9223372036854775808.0 <= d < 9223372036854775808.0):
        raise OverflowError("timestamp out of range for C PyTime_t")
    return int(d)


def _ns_to_seconds(ns: int) -> float:            # PyTime_AsSecondsDouble
    if ns % _SEC_TO_NS == 0:
        return float(ns // _SEC_TO_NS)
    return ns / 1e9


def _clock_ns(clk_id: int) -> int:               # a clock's reading in nanoseconds (_PyTime_FromTimespec)
    result = _sys("clock_gettime", clk_id)
    if type(result) is int:
        _fail(-result)
    sec, nsec = result
    return sec * _SEC_TO_NS + nsec


def _clock_float(clk_id: int) -> float:          # time_clock_gettime_impl: tv_sec + tv_nsec * 1e-9
    result = _sys("clock_gettime", clk_id)
    if type(result) is int:
        _fail(-result)
    sec, nsec = result
    return sec + nsec * 1e-9


def _clockid(value: object) -> int:              # time_clockid_converter: PyLong_AsInt, every failure a TypeError
    try:
        n = _index(value)
    except Exception:
        raise TypeError("clk_id should be integer, not " + _tp_name(value)) from None
    if n < _INT_MIN or n > _INT_MAX:
        raise TypeError("clk_id should be integer, not " + _tp_name(value))
    return n


def _c_int(value: object) -> int:                # PyArg_ParseTuple's "i": PyLong_AsLong, then the int's range
    n = _index(value)
    if n > _INT_MAX:
        raise OverflowError("signed integer is greater than maximum")
    if n < _INT_MIN:
        raise OverflowError("signed integer is less than minimum")
    return n


def _noargs(name: str, args: tuple[object, ...], kwds: dict[str, object]) -> None:   # METH_NOARGS
    if kwds:
        raise TypeError("time." + name + "() takes no keyword arguments")
    if args:
        raise TypeError("time." + name + "() takes no arguments (" + str(len(args)) + " given)")


def _varargs(name: str, args: tuple[object, ...], kwds: dict[str, object], low: int, high: int) -> None:   # METH_VARARGS, PyArg_ParseTuple
    if kwds:
        raise TypeError(name + "() takes no keyword arguments")
    if len(args) < low or len(args) > high:
        if low == high:
            raise TypeError(name + "() takes exactly " + str(low) + " argument" + ("" if low == 1 else "s") + " (" + str(len(args)) + " given)")
        if len(args) < low:
            raise TypeError(name + "() takes at least " + str(low) + " argument" + ("" if low == 1 else "s") + " (" + str(len(args)) + " given)")
        raise TypeError(name + "() takes at most " + str(high) + " argument" + ("" if high == 1 else "s") + " (" + str(len(args)) + " given)")


def _one(name: str, args: tuple[object, ...], kwds: dict[str, object]) -> object:   # METH_O
    if kwds:
        raise TypeError("time." + name + "() takes no keyword arguments")
    if len(args) != 1:
        raise TypeError("time." + name + "() takes exactly one argument (" + str(len(args)) + " given)")
    return args[0]


# ---- the clocks -------------------------------------------------------------------------------------------------------------

def time(*args: object, **kwds: object) -> float:
    """time() -> floating-point number

Return the current time in seconds since the Epoch.
Fractions of a second may be present if the system clock provides them."""
    _noargs("time", args, kwds)
    return _ns_to_seconds(_clock_ns(CLOCK_REALTIME))


def time_ns(*args: object, **kwds: object) -> int:
    """time_ns() -> int

Return the current time in nanoseconds since the Epoch."""
    _noargs("time_ns", args, kwds)
    return _clock_ns(CLOCK_REALTIME)


def monotonic(*args: object, **kwds: object) -> float:
    """monotonic() -> float

Monotonic clock, cannot go backward."""
    _noargs("monotonic", args, kwds)
    return _ns_to_seconds(_clock_ns(CLOCK_MONOTONIC))


def monotonic_ns(*args: object, **kwds: object) -> int:
    """monotonic_ns() -> int

Monotonic clock, cannot go backward, as nanoseconds."""
    _noargs("monotonic_ns", args, kwds)
    return _clock_ns(CLOCK_MONOTONIC)


def perf_counter(*args: object, **kwds: object) -> float:
    """perf_counter() -> float

Performance counter for benchmarking."""
    _noargs("perf_counter", args, kwds)
    return _ns_to_seconds(_clock_ns(CLOCK_MONOTONIC))


def perf_counter_ns(*args: object, **kwds: object) -> int:
    """perf_counter_ns() -> int

Performance counter for benchmarking as nanoseconds."""
    _noargs("perf_counter_ns", args, kwds)
    return _clock_ns(CLOCK_MONOTONIC)


def process_time(*args: object, **kwds: object) -> float:
    """process_time() -> float

Process time for profiling: sum of the kernel and user-space CPU time."""
    _noargs("process_time", args, kwds)
    return _ns_to_seconds(_clock_ns(CLOCK_PROCESS_CPUTIME_ID))


def process_time_ns(*args: object, **kwds: object) -> int:
    """process_time() -> int

Process time for profiling as nanoseconds:
sum of the kernel and user-space CPU time."""
    _noargs("process_time_ns", args, kwds)
    return _clock_ns(CLOCK_PROCESS_CPUTIME_ID)


def thread_time(*args: object, **kwds: object) -> float:
    """thread_time() -> float

Thread time for profiling: sum of the kernel and user-space CPU time."""
    _noargs("thread_time", args, kwds)
    return _ns_to_seconds(_clock_ns(CLOCK_THREAD_CPUTIME_ID))


def thread_time_ns(*args: object, **kwds: object) -> int:
    """thread_time() -> int

Thread time for profiling as nanoseconds:
sum of the kernel and user-space CPU time."""
    _noargs("thread_time_ns", args, kwds)
    return _clock_ns(CLOCK_THREAD_CPUTIME_ID)


def clock_gettime(*args: object, **kwds: object) -> float:
    """Return the time of the specified clock clk_id as a float."""
    return _clock_float(_clockid(_one("clock_gettime", args, kwds)))


def clock_gettime_ns(*args: object, **kwds: object) -> int:
    """Return the time of the specified clock clk_id as nanoseconds (int)."""
    return _clock_ns(_clockid(_one("clock_gettime_ns", args, kwds)))


def clock_settime(*args: object, **kwds: object) -> None:
    """clock_settime(clk_id, time)

Set the time of the specified clock clk_id."""
    _varargs("clock_settime", args, kwds, 2, 2)
    clk_id = _c_int(args[0])
    ns = _seconds_to_ns(args[1], False)
    result = _sys("clock_settime", clk_id, ns // _SEC_TO_NS, ns % _SEC_TO_NS)
    if result < 0:
        _fail(-result)


def clock_settime_ns(*args: object, **kwds: object) -> None:
    """clock_settime_ns(clk_id, time)

Set the time of the specified clock clk_id with nanoseconds."""
    _varargs("clock_settime", args, kwds, 2, 2)
    clk_id = _c_int(args[0])
    ns = _index(args[1])
    if ns < -(2**63) or ns > 2**63 - 1:
        raise OverflowError("Python int too large to convert to C int64_t")
    result = _sys("clock_settime", clk_id, ns // _SEC_TO_NS, ns % _SEC_TO_NS)
    if result < 0:
        _fail(-result)


def clock_getres(*args: object, **kwds: object) -> float:
    """clock_getres(clk_id) -> floating-point number

Return the resolution (precision) of the specified clock clk_id."""
    _varargs("clock_getres", args, kwds, 1, 1)
    result = _sys("clock_getres", _c_int(args[0]))
    if type(result) is int:
        _fail(-result)
    sec, nsec = result
    return sec + nsec * 1e-9


def pthread_getcpuclockid(*args: object, **kwds: object) -> int:
    """pthread_getcpuclockid(thread_id) -> int

Return the clk_id of a thread's CPU time clock."""
    _varargs("pthread_getcpuclockid", args, kwds, 1, 1)
    if not issubclass(type(args[0]), int):        # "k": an int (no __index__), masked to unsigned long
        raise TypeError("pthread_getcpuclockid() argument 1 must be int, not " + _tp_name(args[0]))
    thread_id = int.__index__(args[0]) & (2**64 - 1)  # type: ignore[arg-type]
    result = _sys("pthread_getcpuclockid", thread_id)
    if type(result) is int:
        _fail(-result)
    return result[0]


def sleep(*args: object, **kwds: object) -> None:
    """sleep(seconds)

Delay execution for a given number of seconds.  The argument may be
a floating-point number for subsecond precision."""
    value = _one("sleep", args, kwds)
    ns = _seconds_to_ns(value, True)
    if ns < 0:
        raise ValueError("sleep length must be non-negative")
    result = _sys("nanosleep", ns)
    if type(result) is int:
        _fail(-result)


def get_clock_info(*args: object, **kwds: object) -> object:
    """get_clock_info(name: str) -> dict

Get information of the specified clock."""
    _varargs("get_clock_info", args, kwds, 1, 1)
    name = args[0]
    if not issubclass(type(name), str):
        raise TypeError("get_clock_info() argument 1 must be str, not " + _tp_name(name))
    if "\x00" in name:  # type: ignore[operator]
        raise ValueError("embedded null character")
    clocks = {"time": (CLOCK_REALTIME, "clock_gettime(CLOCK_REALTIME)", False, True), "monotonic": (CLOCK_MONOTONIC, "clock_gettime(CLOCK_MONOTONIC)", True, False),
              "perf_counter": (CLOCK_MONOTONIC, "clock_gettime(CLOCK_MONOTONIC)", True, False),
              "process_time": (CLOCK_PROCESS_CPUTIME_ID, "clock_gettime(CLOCK_PROCESS_CPUTIME_ID)", True, False),
              "thread_time": (CLOCK_THREAD_CPUTIME_ID, "clock_gettime(CLOCK_THREAD_CPUTIME_ID)", True, False)}
    entry = clocks.get(name)  # type: ignore[call-overload]
    if entry is None:
        raise ValueError("unknown clock")
    clk_id, implementation, is_monotonic, adjustable = entry
    _clock_ns(clk_id)
    result = _sys("clock_getres", clk_id)
    if type(result) is int:
        _fail(-result)
    sec, nsec = result
    return _bella_bootstrap("SimpleNamespace", {"implementation": implementation, "monotonic": is_monotonic, "adjustable": adjustable,
                                                "resolution": sec + nsec * 1e-9})


# ---- struct tm both ways (tmtotuple, gettmarg, checktm) -----------------------------------------------------------------------

def _tm_to_struct(fields: tuple[object, ...]) -> object:   # tmtotuple: the C ranges to Python's
    year, mon, mday, hour, minute, sec, wday, yday, isdst, zone, gmtoff = fields
    return struct_time((year + 1900, mon + 1, mday, hour, minute, sec, (wday + 6) % 7, yday + 1, isdst,  # type: ignore[operator]
                        bytes.decode(zone, "utf-8", "surrogateescape"), gmtoff))  # type: ignore[arg-type]


def _time_t_arg(name: str, args: tuple[object, ...], kwds: dict[str, object]) -> int:   # parse_time_t_args: "|O"
    _varargs(name, args, kwds, 0, 1)
    if not args or args[0] is None:
        return _clock_ns(CLOCK_REALTIME) // _SEC_TO_NS
    return _object_to_time_t(args[0])


def _broken_down(which: str, t: int) -> tuple[object, ...]:   # _PyTime_gmtime, _PyTime_localtime
    if t < _TIME_T_MIN or t > _TIME_T_MAX:
        raise OverflowError("timestamp out of range for platform time_t")
    result = _sys(which, t)
    if type(result) is int:                      # EOVERFLOW from the library is an OSError, as the C leaves it
        _fail(-result)
    return result  # type: ignore[no-any-return]


def gmtime(*args: object, **kwds: object) -> object:
    """gmtime([seconds]) -> (tm_year, tm_mon, tm_mday, tm_hour, tm_min,
                       tm_sec, tm_wday, tm_yday, tm_isdst)

Convert seconds since the Epoch to a time tuple expressing UTC (a.k.a.
GMT).  When 'seconds' is not passed in, convert the current time instead.

If the platform supports the tm_gmtoff and tm_zone, they are available as
attributes only."""
    return _tm_to_struct(_broken_down("gmtime", _time_t_arg("gmtime", args, kwds)))


def localtime(*args: object, **kwds: object) -> object:
    """localtime([seconds]) -> (tm_year,tm_mon,tm_mday,tm_hour,tm_min,
                          tm_sec,tm_wday,tm_yday,tm_isdst)

Convert seconds since the Epoch to a time tuple expressing local time.
When 'seconds' is not passed in, convert the current time instead."""
    return _tm_to_struct(_broken_down("localtime", _time_t_arg("localtime", args, kwds)))


def _c_mod(a: int, n: int) -> int:               # C's %, the remainder taking the dividend's sign
    r = abs(a) % n
    return -r if a < 0 else r


def _gettmarg(value: object, message: str) -> list[object]:
    """gettmarg: the nine fields in C's ranges, then tm_zone (bytes or None) and tm_gmtoff (int or None) from a struct_time."""
    if not issubclass(type(value), tuple):
        raise TypeError("Tuple or struct_time argument required")
    if tuple.__len__(value) != 9:  # type: ignore[arg-type]
        raise TypeError(message)
    items = [_c_int(tuple.__getitem__(value, i)) for i in range(9)]  # type: ignore[arg-type]
    year = items[0]
    if year < _INT_MIN + 1900:
        raise OverflowError("year out of range")
    out: list[object] = [year - 1900, items[1] - 1, items[2], items[3], items[4], items[5], _c_mod(items[6] + 1, 7), items[7] - 1, items[8], None, None]   # (tm_wday + 1) % 7 in C: negative stays negative
    if type(value) is struct_time:
        zone = value.tm_zone  # type: ignore[attr-defined]
        if zone is not None:
            if not issubclass(type(zone), str):
                raise TypeError("bad argument type for built-in operation")
            out[9] = str.encode(zone, "utf-8", "surrogateescape")   # PyUnicode_AsUTF8: the C reads it up to a NUL
        gmtoff = value.tm_gmtoff  # type: ignore[attr-defined]
        if gmtoff is not None:
            n = _index(gmtoff)
            if n < -(2**63) or n > 2**63 - 1:
                raise OverflowError("Python int too large to convert to C long")
            out[10] = n
    return out


def _checktm(tm: list[object]) -> None:          # checktm, before strftime and asctime
    mon, mday, hour, minute, sec, wday, yday = tm[1], tm[2], tm[3], tm[4], tm[5], tm[6], tm[7]
    if mon == -1:
        tm[1] = 0
    elif mon < 0 or mon > 11:  # type: ignore[operator]
        raise ValueError("month out of range")
    if mday == 0:
        tm[2] = 1
    elif mday < 0 or mday > 31:  # type: ignore[operator]
        raise ValueError("day of month out of range")
    if hour < 0 or hour > 23:  # type: ignore[operator]
        raise ValueError("hour out of range")
    if minute < 0 or minute > 59:  # type: ignore[operator]
        raise ValueError("minute out of range")
    if sec < 0 or sec > 61:  # type: ignore[operator]
        raise ValueError("seconds out of range")
    if wday < 0:  # type: ignore[operator]
        raise ValueError("day of week out of range")
    if yday == -1:
        tm[7] = 0
    elif yday < 0 or yday > 365:  # type: ignore[operator]
        raise ValueError("day of year out of range")


def _now_local() -> list[object]:
    return list(_broken_down("localtime", _clock_ns(CLOCK_REALTIME) // _SEC_TO_NS))


def mktime(*args: object, **kwds: object) -> float:
    """mktime(time_tuple) -> floating-point number

Convert a time tuple in local time to seconds since the Epoch.
Note that mktime(gmtime(0)) will not generally return zero for most
time zones; instead the returned value will either be equal to that
of the timezone or altzone attributes on the time module."""
    tm = _gettmarg(_one("mktime", args, kwds), "mktime(): illegal time tuple argument")
    result = _sys("mktime", *tm)
    if result is None:
        raise OverflowError("mktime argument out of range")
    return float(result)


def _asctime(tm: list[object]) -> str:           # _asctime: "%s %s%3d %.2d:%.2d:%.2d %d"
    wday_name = ("Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat")
    mon_name = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")
    year, mon, mday, hour, minute, sec, wday = tm[0], tm[1], tm[2], tm[3], tm[4], tm[5], tm[6]
    return (wday_name[wday] + " " + mon_name[mon] + str(mday).rjust(3) + " " + _two(hour) + ":" + _two(minute) + ":" + _two(sec)  # type: ignore[index]
            + " " + str(1900 + year))  # type: ignore[operator]


def _two(n: object) -> str:                      # %.2d
    text = str(n)
    if text[:1] == "-":
        return "-" + text[1:].rjust(2, "0")
    return text.rjust(2, "0")


def asctime(*args: object, **kwds: object) -> str:
    """asctime([time_tuple]) -> string

Convert a time tuple to a string, e.g. 'Sat Jun 06 16:26:11 1998'.
When the time tuple is not present, current time as returned by localtime()
is used."""
    if kwds:
        raise TypeError("time.asctime() takes no keyword arguments")
    if len(args) > 1:
        raise TypeError("asctime expected at most 1 argument, got " + str(len(args)))
    if not args:
        tm = _now_local()
    else:
        tm = _gettmarg(args[0], "asctime(): illegal time tuple argument")
        _checktm(tm)
    return _asctime(tm)


def ctime(*args: object, **kwds: object) -> str:
    """ctime([seconds]) -> string

Convert a time in seconds since the Epoch to a string in local time.
This is equivalent to asctime(localtime(seconds)). When 'seconds' is not
passed in, convert the current time instead."""
    return _asctime(list(_broken_down("localtime", _time_t_arg("ctime", args, kwds))))


def strftime(*args: object, **kwds: object) -> str:
    """strftime(format[, time_tuple]) -> string

Convert a time tuple to a string according to a format specification.
See the library reference manual for formatting codes. When the time tuple
is not present, current time as returned by localtime() is used.

Commonly used format codes:

%Y  Year with century as a decimal number.
%m  Month as a decimal number [01,12].
%d  Day of the month as a decimal number [01,31].
%H  Hour (24-hour clock) as a decimal number [00,23].
%M  Minute as a decimal number [00,59].
%S  Second as a decimal number [00,61].
%z  Time zone offset from UTC.
%a  Locale's abbreviated weekday name.
%A  Locale's full weekday name.
%b  Locale's abbreviated month name.
%B  Locale's full month name.
%c  Locale's appropriate date and time representation.
%I  Hour (12-hour clock) as a decimal number [01,12].
%p  Locale's equivalent of either AM or PM.

Other codes may be available on your platform.  See documentation for
the C library strftime function.
"""
    _varargs("strftime", args, kwds, 1, 2)
    fmt = args[0]
    if not issubclass(type(fmt), str):
        raise TypeError("strftime() argument 1 must be str, not " + _tp_name(fmt))
    if len(args) == 1:
        tm = _now_local()
    else:
        tm = _gettmarg(args[1], "strftime(): illegal time tuple argument")
        _checktm(tm)
    if tm[8] < -1:  # type: ignore[operator]
        tm[8] = -1
    elif tm[8] > 1:  # type: ignore[operator]
        tm[8] = 1
    text = str.__str__(fmt)  # type: ignore[arg-type]  # the text itself, whatever a subclass's __str__ says
    out: list[str] = []
    i = 0
    n = len(text)
    while i < n:                                 # an ASCII run through the C's strftime, then the rest up to the next % as it is
        start = i
        while i < n and "\x01" <= text[i] <= "\x7f":
            i += 1
        if i > start:
            piece = _sys("strftime", str.encode(text[start:i], "ascii"), *tm)
            out.append(bytes.decode(piece, "utf-8", "surrogateescape"))
        start = i
        while i < n and text[i] != "%":
            i += 1
        out.append(text[start:i])
    return "".join(out)


def strptime(*args: object, **kwds: object) -> object:
    """strptime(string[, format]) -> struct_time

Parse a string to a time tuple according to a format specification.
See the library reference manual for formatting codes (same as
strftime()).

Commonly used format codes:

%Y  Year with century as a decimal number.
%m  Month as a decimal number [01,12].
%d  Day of the month as a decimal number [01,31].
%H  Hour (24-hour clock) as a decimal number [00,23].
%M  Minute as a decimal number [00,59].
%S  Second as a decimal number [00,61].
%z  Time zone offset from UTC.
%a  Locale's abbreviated weekday name.
%A  Locale's full weekday name.
%b  Locale's abbreviated month name.
%B  Locale's full month name.
%c  Locale's appropriate date and time representation.
%I  Hour (12-hour clock) as a decimal number [01,12].
%p  Locale's equivalent of either AM or PM.

Other codes may be available on your platform.  See documentation for
the C library strftime function.
"""
    if kwds:
        raise TypeError("time.strptime() takes no keyword arguments")
    import _strptime
    return _strptime._strptime_time(*args)


# ---- the time zone (init_timezone) ------------------------------------------------------------------------------------------

timezone = 0
altzone = 0
daylight = 0
tzname = ("", "")


def _init_timezone(imported: bool) -> None:
    """init_timezone as this build has it (no HAVE_DECL_TZNAME): tzset, then the local time of a January and a July of the current
    year decide timezone, altzone, daylight and tzname; the zone names are at most nine characters."""
    global timezone, altzone, daylight, tzname
    _sys("tzset")
    year = (365 * 24 + 6) * 3600
    t = (_clock_ns(CLOCK_REALTIME) // _SEC_TO_NS) // year * year
    jan = _broken_down("localtime", t)
    janname, janzone = _zone_name(jan), -jan[10]  # type: ignore[operator]
    july = _broken_down("localtime", t + year // 2)
    julyname, julyzone = _zone_name(july), -july[10]  # type: ignore[operator]
    if not (-48 * 3600 <= janzone <= 48 * 3600) or not (-48 * 3600 <= julyzone <= 48 * 3600):
        raise RuntimeError("invalid GMT offset")
    if janzone < julyzone:
        timezone, altzone, tzname = julyzone, janzone, (julyname, janname)
    else:
        timezone, altzone, tzname = janzone, julyzone, (janname, julyname)
    daylight = int(janzone != julyzone)
    if imported:                                 # the module has its own copy of these names once imported
        _bella_module_set("timezone", timezone)
        _bella_module_set("altzone", altzone)
        _bella_module_set("daylight", daylight)
        _bella_module_set("tzname", tzname)


def _zone_name(tm: tuple[object, ...]) -> str:   # get_zone: strncpy of tm_zone (or three spaces) into nine characters
    zone = tm[9]
    data = zone if zone else b"   "  # type: ignore[truthy-bool]
    return bytes.decode(data[:9], "utf-8", "surrogateescape")  # type: ignore[index]


def tzset(*args: object, **kwds: object) -> None:
    """tzset()

Initialize, or reinitialize, the local timezone to the value stored in
os.environ['TZ']. The TZ environment variable should be specified in
standard Unix timezone format as documented in the tzset man page
(eg. 'US/Eastern', 'Europe/Amsterdam'). Unknown timezones will silently
fall back to UTC. If the TZ environment variable is not set, the local
timezone is set to the systems best guess of wallclock time.
Changing the TZ environment variable without calling tzset *may* change
the local timezone used by methods such as localtime, but this behaviour
should not be relied on."""
    _noargs("tzset", args, kwds)
    _init_timezone(True)


_init_timezone(False)
