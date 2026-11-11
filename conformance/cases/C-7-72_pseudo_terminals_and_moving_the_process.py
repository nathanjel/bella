# clause: C-7-72
# spec: section 7
# status: P1
# source: dialect specification section 7 (os), Modules/posixmodule.c (os_openpty_impl, os_ttyname_impl, os_posix_openpt_impl, os_grantpt_impl, os_unlockpt_impl, os_ptsname_impl, os_tcgetpgrp_impl, os_tcsetpgrp_impl, os_login_tty_impl, os_chroot_impl, os_unshare_impl, os_setns_impl)
"""Pseudo-terminals and what is asked of a terminal: openpty, posix_openpt with grantpt, unlockpt and ptsname, ttyname,
tcgetpgrp and tcsetpgrp, login_tty; and three calls that move the process elsewhere, chroot, unshare and setns, as far as a
process without the privilege gets. What each returns, what it refuses, and what its OSError carries."""
# ruff: noqa: E501, PTH
# A pseudo-terminal's name is the machine's (/dev/pts/ and a number, and the multiplexer is /dev/ptmx or /dev/pts/ptmx): what is
# printed is where it is and that two ways of asking agree.
import os
import stat
import tempfile
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


class Fileno:
    def __init__(self, fd: int) -> None:
        self.fd = fd

    def fileno(self) -> int:
        return self.fd


def main() -> None:
    d = tempfile.mkdtemp()
    name = os.path.join(d, "f")
    with open(name, "wb") as f:
        f.write(b"x")
    plain = os.open(name, os.O_RDONLY)

    # a pair: neither end inherited, both terminals, and what is written to one end is read at the other
    master, slave = os.openpty()
    os.write(slave, b"to the master\n")
    arrived = os.read(master, 100)
    os.write(master, b"to the slave\n")
    print("openpty:", master > 2, slave > 2, master != slave, os.get_inheritable(master), os.get_inheritable(slave), os.isatty(master), os.isatty(slave), stat.S_ISCHR(os.fstat(slave).st_mode), arrived, os.read(slave, 100),
          os.device_encoding(slave), m(lambda: os.openpty(1)), m(lambda: os.openpty(x=1)))  # type: ignore[call-arg]
    shown = os.ttyname(slave)
    print("ttyname:", type(shown).__name__, shown.startswith("/dev/pts/"), shown[9:].isdigit(), os.ptsname(master) == shown, os.ttyname(master).endswith("/ptmx"), os.stat(os.ttyname(master)).st_rdev == os.fstat(master).st_rdev, os.ttyname(Index(slave)) == shown, os.stat(shown).st_rdev == os.fstat(slave).st_rdev,  # type: ignore[arg-type]
          m(lambda: os.ttyname(plain)), m(lambda: os.ttyname(987)), m(lambda: os.ttyname("x")), m(lambda: os.ttyname()), m(lambda: os.ttyname(fd=slave)), m(lambda: os.ttyname(1.5)), m(lambda: os.ttyname(2**40)),  # type: ignore[arg-type, call-arg]
          m(lambda: os.ttyname(Fileno(slave))))  # type: ignore[arg-type]

    # the same by hand: open the multiplexer, grant, unlock, and ask for the other end's name
    multiplexer = os.posix_openpt(os.O_RDWR | os.O_NOCTTY)
    print("posix_openpt:", multiplexer > 2, os.get_inheritable(multiplexer), os.isatty(multiplexer), os.grantpt(multiplexer), os.unlockpt(multiplexer), os.ptsname(multiplexer).startswith("/dev/pts/"),  # type: ignore[func-returns-value]
          os.ptsname(multiplexer) != shown, os.grantpt(Fileno(multiplexer)), os.unlockpt(Fileno(multiplexer)), os.ptsname(Fileno(multiplexer)) == os.ptsname(multiplexer), os.isatty(os.open(os.ptsname(multiplexer), os.O_RDWR | os.O_NOCTTY)),  # type: ignore[func-returns-value]
          os.posix_openpt(Index(os.O_RDWR)) > 2)  # type: ignore[arg-type]
    print("they refuse:", m(lambda: os.posix_openpt()), m(lambda: os.posix_openpt("x")), m(lambda: os.posix_openpt(oflag=2)), m(lambda: os.posix_openpt(2**40)), m(lambda: os.posix_openpt(2, 3)), m(lambda: os.grantpt(987)),  # type: ignore[call-arg, arg-type]
          m(lambda: os.grantpt(plain)), m(lambda: os.grantpt(slave)), m(lambda: os.grantpt("x")), m(lambda: os.grantpt()), m(lambda: os.grantpt(fd=multiplexer)), m(lambda: os.unlockpt(987)), m(lambda: os.unlockpt(plain)),  # type: ignore[arg-type, call-arg]
          m(lambda: os.unlockpt(slave)), m(lambda: os.unlockpt()), m(lambda: os.unlockpt(1.5)), m(lambda: os.ptsname(987)), m(lambda: os.ptsname(plain)), m(lambda: os.ptsname(slave)), m(lambda: os.ptsname()), m(lambda: os.ptsname("x")),  # type: ignore[call-arg, arg-type]
          m(lambda: os.ptsname(fd=multiplexer)))  # type: ignore[call-arg]

    # the terminal's foreground group: a terminal that is not this process's own has none to give or take
    print("tcgetpgrp and tcsetpgrp:", os.tcgetpgrp(master), m(lambda: os.tcgetpgrp(slave)), m(lambda: os.tcgetpgrp(plain)), m(lambda: os.tcgetpgrp(987)), m(lambda: os.tcgetpgrp("x")), m(lambda: os.tcgetpgrp()), m(lambda: os.tcgetpgrp(fd=slave)),  # type: ignore[arg-type, call-arg]
          m(lambda: os.tcgetpgrp(Fileno(slave))), m(lambda: os.tcgetpgrp(1.5)), m(lambda: os.tcsetpgrp(slave, os.getpgrp())), m(lambda: os.tcsetpgrp(plain, os.getpgrp())), m(lambda: os.tcsetpgrp(987, 1)), m(lambda: os.tcsetpgrp(slave)),  # type: ignore[arg-type, call-arg]
          m(lambda: os.tcsetpgrp("x", 1)), m(lambda: os.tcsetpgrp(slave, "x")), m(lambda: os.tcsetpgrp(fd=slave, pgid=1)), m(lambda: os.tcsetpgrp(slave, 2**40)), m(lambda: os.tcsetpgrp(slave, 1, 2)), m(lambda: os.tcsetpgrp(slave, -1)))  # type: ignore[arg-type, call-arg]
    print("login_tty refuses:", m(lambda: os.login_tty(987)), m(lambda: os.login_tty("x")), m(lambda: os.login_tty()), m(lambda: os.login_tty(fd=slave)), m(lambda: os.login_tty(Fileno(987))), m(lambda: os.login_tty(1.5)))  # type: ignore[arg-type, call-arg]

    # elsewhere: a root that is not there; of unshare and setns, what is refused before the system is asked (a container's
    # filter answers the calls themselves in its own way, so those are compared on one machine only)
    print("chroot, unshare and setns:", m(lambda: os.chroot(os.path.join(d, "missing"))) == "FileNotFoundError: " + repr((2, "No such file or directory", os.path.join(d, "missing"))),
          m(lambda: os.chroot(os.fsencode(name))) == "NotADirectoryError: " + repr((20, "Not a directory", os.fsencode(name))), m(lambda: os.chroot(path=name)) == "NotADirectoryError: " + repr((20, "Not a directory", name)),
          m(lambda: os.chroot(5)), m(lambda: os.chroot()), m(lambda: os.chroot("a\0b")), m(lambda: os.chroot(name, 1)), m(lambda: os.chroot(None)), m(lambda: os.unshare()),  # type: ignore[arg-type, call-arg]
          m(lambda: os.unshare("x")), m(lambda: os.unshare(2**40)), m(lambda: os.unshare(0, 0)), m(lambda: os.unshare(flag=0)), m(lambda: os.setns()), m(lambda: os.setns("x")),  # type: ignore[arg-type, call-arg]
          m(lambda: os.setns(987, "x")), m(lambda: os.setns(987, 0, 0)), m(lambda: os.setns(Fileno("x"))), m(lambda: os.setns(987, 2**40)), m(lambda: os.setns(987, nstyp=0)), m(lambda: os.setns(1.5)))  # type: ignore[arg-type, call-arg]

    for descriptor in (plain, master, slave, multiplexer):
        os.close(descriptor)
    os.unlink(name)
    os.rmdir(d)


if __name__ == "__main__":
    main()
