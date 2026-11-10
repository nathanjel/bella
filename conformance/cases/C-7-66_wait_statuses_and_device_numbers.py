# clause: C-7-66
# spec: section 7
# status: P1
# source: dialect specification section 7 (os), Modules/posixmodule.c (os_WCOREDUMP_impl to os_WSTOPSIG_impl, os_waitstatus_to_exitcode_impl, _Py_Dev_Converter, os_major_impl, os_minor_impl, os_makedev_impl, major_minor_conv, _PyLong_FromDev)
"""The functions of os that only compute: what a wait status says (the eight tests and parts of it, and the exit code it stands
for), and a device number taken apart and put together, with -1 for no device. What each takes, by position or by name, and
what it refuses."""
# ruff: noqa: E501
import os
from collections.abc import Callable


def m(f: Callable[[], object]) -> str:
    try:
        return repr(f())
    except Exception as e:
        return type(e).__name__


def call(f: object, *args: object, **kwds: object) -> str:
    try:
        return repr(f(*args, **kwds))  # type: ignore[operator]
    except Exception as e:
        return type(e).__name__


class Index:
    def __init__(self, value: int) -> None:
        self.value = value

    def __index__(self) -> int:
        return self.value


STATUSES = [0, 1, 2, 9, 11, 15, 0x7e, 0x7f, 0x80, 0x81, 0x8b, 0xff, 0x100, 0x137f, 0x1300, 0x2a00, 0xff00, 0xff7f, 0xffff, 0x10000, 0x1007f, 0x7fffffff, -1, -2, -256, -0x80000000]


def main() -> None:
    for status in STATUSES:
        print(status, os.WIFEXITED(status), os.WEXITSTATUS(status), os.WIFSIGNALED(status), os.WTERMSIG(status), os.WCOREDUMP(status), os.WIFSTOPPED(status), os.WSTOPSIG(status), os.WIFCONTINUED(status),
              call(os.waitstatus_to_exitcode, status))
    print("every status of two bytes:", sum(os.WIFEXITED(s) for s in range(0x10000)), sum(os.WIFSIGNALED(s) for s in range(0x10000)), sum(os.WIFSTOPPED(s) for s in range(0x10000)),
          sum(os.WIFCONTINUED(s) for s in range(0x10000)), sum(os.WCOREDUMP(s) for s in range(0x10000)), sum(os.WEXITSTATUS(s) + os.WTERMSIG(s) + os.WSTOPSIG(s) for s in range(0x10000)),
          sum(1 for s in range(0x10000) if call(os.waitstatus_to_exitcode, s) == "ValueError"), sum(os.waitstatus_to_exitcode(s) for s in range(0x10000) if os.WIFEXITED(s) or os.WIFSIGNALED(s)))
    print("types:", type(os.WIFEXITED(0)).__name__, type(os.WEXITSTATUS(0)).__name__, type(os.WIFSIGNALED(0)).__name__, type(os.WTERMSIG(0)).__name__, type(os.WCOREDUMP(0)).__name__, type(os.WIFSTOPPED(0)).__name__,
          type(os.WSTOPSIG(0)).__name__, type(os.WIFCONTINUED(0)).__name__, type(os.waitstatus_to_exitcode(0)).__name__)
    print("by name:", os.WIFEXITED(status=0), os.WEXITSTATUS(status=0x300), os.WIFSIGNALED(status=9), os.WTERMSIG(status=9), os.WIFSTOPPED(status=0x7f), os.WSTOPSIG(status=0x137f), os.WIFCONTINUED(status=0xffff),
          os.waitstatus_to_exitcode(status=0x200), m(lambda: os.WCOREDUMP(status=0)), os.WIFEXITED(Index(0)), os.WEXITSTATUS(True), os.waitstatus_to_exitcode(Index(9)), os.waitstatus_to_exitcode(True))  # type: ignore[call-arg, arg-type]
    for name in ("WIFEXITED", "WEXITSTATUS", "WIFSIGNALED", "WTERMSIG", "WCOREDUMP", "WIFSTOPPED", "WSTOPSIG", "WIFCONTINUED", "waitstatus_to_exitcode"):
        f: object = getattr(os, name)
        print(name, "refuses:", call(f, "x"), call(f, 1.5), call(f, None), call(f, 2 ** 31), call(f, -(2 ** 31) - 1), call(f, 2 ** 70), call(f), call(f, 0, 0), call(f, state=0))

    # device numbers
    for major, minor in ((0, 0), (8, 3), (1, 5), (259, 1048575), (4095, 255), (4096, 256), (2 ** 31, 5), (2 ** 32 - 2, 2 ** 32 - 2), (2 ** 32 - 1, 0), (0, 2 ** 32 - 1), (-1, -1), (-1, 0), (0, -1), (12345, 67890)):
        device = os.makedev(major, minor)
        print((major, minor), device, os.major(device), os.minor(device), os.makedev(os.major(device), os.minor(device)) == device)
    for device in (0, 1, 255, 256, 0x0803, 0xfffff, 0x100000, 2 ** 32 - 1, 2 ** 32, 2 ** 44 - 1, 2 ** 44, 2 ** 63, 2 ** 64 - 2, 2 ** 64 - 1, -1):
        print(device, os.major(device), os.minor(device))
    print("types:", type(os.major(0)).__name__, type(os.minor(0)).__name__, type(os.makedev(0, 0)).__name__, os.major(Index(0x0803)), os.minor(Index(0x0803)), os.makedev(Index(8), Index(3)), os.major(True), os.makedev(True, False))  # type: ignore[arg-type]
    print("major refuses:", m(lambda: os.major(-2)), m(lambda: os.major(-(2 ** 70))), m(lambda: os.major(2 ** 64)), m(lambda: os.major(2 ** 70)), m(lambda: os.major(1.5)), m(lambda: os.major("8")), m(lambda: os.major()), m(lambda: os.major(0, 0)),  # type: ignore[arg-type, call-arg]
          m(lambda: os.major(device=0)), m(lambda: os.major(None)))  # type: ignore[call-arg, arg-type]
    print("minor refuses:", m(lambda: os.minor(-2)), m(lambda: os.minor(2 ** 64)), m(lambda: os.minor(1.5)), m(lambda: os.minor("8")), m(lambda: os.minor()), m(lambda: os.minor(device=0)))  # type: ignore[arg-type, call-arg]
    print("makedev refuses:", m(lambda: os.makedev(2 ** 32, 0)), m(lambda: os.makedev(0, 2 ** 32)), m(lambda: os.makedev(2 ** 64 - 1, 0)), m(lambda: os.makedev(-2, 0)), m(lambda: os.makedev(0, -2)), m(lambda: os.makedev(2 ** 64, 0)),
          m(lambda: os.makedev(1.5, 0)), m(lambda: os.makedev(0, "3")), m(lambda: os.makedev(8)), m(lambda: os.makedev(8, 3, 1)), m(lambda: os.makedev(major=8, minor=3)), m(lambda: os.makedev()))  # type: ignore[arg-type, call-arg]


if __name__ == "__main__":
    main()
