# clause: C-8-16
# spec: section 8 (Environment)
# status: P1
# source: Python/initconfig.c (config_read_env_vars, config_init_int_max_str_digits, config_init_cpu_count, config_init_hash_seed),
#         Python/preconfig.c (_Py_GetEnv, _Py_str_to_int, _Py_get_env_flag), Python/pylifecycle.c (create_stdio, fatal_error),
#         Modules/posixmodule.c (os_cpu_count_impl), Lib/os.py (process_cpu_count)
"""The variables of the environment that a program reads when it starts: PYTHONUNBUFFERED (standard output and error
are written at once), PYTHONINTMAXSTRDIGITS (the limit of a conversion between int and str), PYTHON_CPU_COUNT (what
os.cpu_count() says) and PYTHONHASHSEED. The program starts itself again under each setting and prints what the second
one saw. A value that cannot be taken ends the second one before its first line: status 1, and what went wrong on
standard error."""
import io
import os
import sys

SHOW = "BELLA_CASE_SHOW"
WANT = "BELLA_CASE_WANT"


def digits() -> None:
    print("the limit:", sys.get_int_max_str_digits(), "| in sys.flags:", sys.flags.int_max_str_digits)
    for size in (639, 640, 641, 1000, 4300, 4301, 10000):
        try:
            made = f"str makes {len(str(10 ** (size - 1)))}"
        except ValueError:
            made = "str refuses"
        try:
            int("7" * size)
            taken = "int takes them"
        except ValueError:
            taken = "int refuses"
        print(f"{size} digits: {made}, {taken}")
    sys.set_int_max_str_digits(0)                # what the program sets comes after what the variable said
    print("set to 0 by the program:", sys.get_int_max_str_digits(), "| in sys.flags:", sys.flags.int_max_str_digits, "|", len(str(10 ** 9999)))


def cpus() -> None:
    want = os.environ[WANT]
    count = os.cpu_count()
    usable = os.process_cpu_count()
    if want == "the system's":
        print("cpu_count():", "the system's" if count == os.sysconf("SC_NPROCESSORS_ONLN") else "not the system's")
        print("process_cpu_count():", "the CPUs it may run on" if usable == len(os.sched_getaffinity(0)) else "not the CPUs it may run on")
    else:
        print("cpu_count():", "the variable's" if count == int(want) else "not the variable's")
        print("process_cpu_count():", "the variable's" if usable == int(want) else "not the variable's")


def streams() -> None:
    for name, stream in (("stdin", sys.stdin), ("stdout", sys.stdout), ("stderr", sys.stderr)):
        assert isinstance(stream, io.TextIOWrapper)
        print(f"{name}: write_through {stream.write_through}, line_buffering {stream.line_buffering}, over a {type(stream.buffer).__name__}")
    sys.stdout.flush()
    # what is written past a stream comes first when the stream was keeping its own
    sys.stdout.write("through standard output, ")
    os.write(1, b"past it, ")
    sys.stdout.write("through it again\n")
    sys.stdout.flush()
    sys.stderr.write("through standard error, ")
    os.write(2, b"past it, ")
    sys.stderr.write("through it again\n")


def seed() -> None:
    print("hash_randomization:", sys.flags.hash_randomization)
    if os.environ[WANT] == "the same in every run":
        print("hash of a str:", hash("the same text"), "| of bytes:", hash(b"the same bytes"))


def again(show: str, want: str = "", **setting: str) -> None:
    """Start this program again with standard input at /dev/null and both outputs in one pipe; print what it wrote."""
    here, there = os.pipe()
    child = os.posix_spawn(sys.executable, sys.orig_argv, {"PYTHONHASHSEED": "0", SHOW: show, WANT: want} | setting,
                           file_actions=[(os.POSIX_SPAWN_OPEN, 0, "/dev/null", os.O_RDONLY, 0), (os.POSIX_SPAWN_DUP2, there, 1),
                                         (os.POSIX_SPAWN_DUP2, there, 2), (os.POSIX_SPAWN_CLOSE, here)])
    os.close(there)
    wrote = b""
    while chunk := os.read(here, 65536):
        wrote += chunk
    os.close(here)
    status = os.waitstatus_to_exitcode(os.waitpid(child, 0)[1])
    print(", ".join(f"{name}={value!r}" for name, value in setting.items()) or "none of them", "-> status", status)
    for line in wrote.decode().splitlines():
        print("    " + line if line else "    (an empty line)")


def main() -> None:
    print("---- PYTHONUNBUFFERED: any text but a number below one")
    again("streams")
    for value in ("1", "0", "", "yes", "-3", "2", " 1", "00"):
        again("streams", PYTHONUNBUFFERED=value)

    print("---- PYTHONINTMAXSTRDIGITS: 0, or 640 and more")
    again("digits")
    for value in ("0", "640", "1000", " 700", "+800", "2147483647", "", "639", "1", "-1", "2147483648", "99999999999999999999", "700 ", "0x400", "many"):
        again("digits", PYTHONINTMAXSTRDIGITS=value)

    print("---- PYTHON_CPU_COUNT: default, or 1 and more")
    again("cpus", "the system's")
    for value, want in (("1000003", "1000003"), ("1", "1"), (" 7777", "7777"), ("2147483647", "2147483647"), ("default", "the system's"),
                        ("", "the system's"), ("0", ""), ("-2", ""), ("2147483648", ""), ("5x", ""), ("Default", ""), ("many", "")):
        again("cpus", want, PYTHON_CPU_COUNT=value)

    print("---- PYTHONHASHSEED: random, or 0 to 4294967295")
    for value, want in (("0", "the same in every run"), ("7", "the same in every run"), (" 7", "the same in every run"),
                        ("4294967295", "the same in every run"), ("random", ""), ("", ""), ("4294967296", ""), ("-1", ""), ("7x", ""),
                        ("Random", ""), ("seven", "")):
        again("seed", want, PYTHONHASHSEED=value)

    print("---- together; the first that cannot be taken is the one told of")
    again("digits", PYTHONINTMAXSTRDIGITS="640", PYTHON_CPU_COUNT="2", PYTHONUNBUFFERED="1")
    again("digits", PYTHONINTMAXSTRDIGITS="5", PYTHON_CPU_COUNT="0", PYTHONHASHSEED="seven")
    again("digits", PYTHON_CPU_COUNT="0", PYTHONHASHSEED="seven")
    again("digits", PYTHONINTMAXSTRDIGITS="5", PYTHON_CPU_COUNT="0")


if SHOW in os.environ:
    {"digits": digits, "cpus": cpus, "streams": streams, "seed": seed}[os.environ[SHOW]]()
else:
    main()
