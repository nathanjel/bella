# clause: C-7-67
# spec: section 7
# status: P1
# source: dialect specification section 7 (os), Modules/posixmodule.c (os_chown_impl, os_fchown_impl, os_lchown_impl, _Py_Uid_Converter, _Py_Gid_Converter, os_getgroups_impl, os_getpgid_impl, os_getpgrp_impl, os_getsid_impl, os_getresuid_impl, os_getresgid_impl, os_getpriority_impl, os_nice_impl, os_getloadavg_impl, os_sched_yield_impl, os_getrandom_impl)
"""Who owns a file and who the process is. chown by name, by descriptor, under a directory's descriptor and for a link itself,
fchown and lchown, with -1 for "leave it"; how a user or group id converts and what it refuses; the ids, groups, process group
and session of the process, its priority, the load averages, sched_yield and getrandom."""
# ruff: noqa: E501, PTH
# The ids are the environment's own (a user here, root in an image): what is printed is how they relate, and a file is only
# ever given to the owner it has, which every user may do.
import os
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


NO_PROCESS = 4194305                             # above the largest process id the kernel gives out


def main() -> None:
    d = tempfile.mkdtemp()
    os.chdir(d)
    with open("f", "wb") as f:
        f.write(b"x")
    os.symlink("f", "ln")
    os.symlink("nowhere", "dangling")
    fd = os.open("f", os.O_RDONLY)
    top = os.open(d, os.O_RDONLY)
    uid, gid = os.getuid(), os.getgid()

    def owner(name: str, follow: bool = True) -> bool:
        st = os.stat(name, follow_symlinks=follow)
        return (st.st_uid, st.st_gid) == (uid, gid)

    print("chown:", m(lambda: os.chown("f", uid, gid)), m(lambda: os.chown("f", -1, -1)), m(lambda: os.chown("f", uid, -1)), m(lambda: os.chown(b"f", -1, gid)), m(lambda: os.chown(path="f", uid=-1, gid=-1)),
          m(lambda: os.chown("ln", uid, gid)), m(lambda: os.chown("ln", uid, gid, follow_symlinks=False)), m(lambda: os.chown("dangling", -1, -1)), m(lambda: os.chown("dangling", uid, gid, follow_symlinks=False)),
          m(lambda: os.chown(fd, uid, gid)), m(lambda: os.chown("f", Index(uid), Index(gid))), m(lambda: os.chown("f", 2 ** 32 - 1, 2 ** 32 - 1)), owner("f"), owner("ln", False), owner("dangling", False))  # type: ignore[arg-type]
    os.chdir("/")
    print("under a directory:", m(lambda: os.chown("f", uid, gid, dir_fd=top)), m(lambda: os.chown("dangling", uid, gid, dir_fd=top, follow_symlinks=False)), m(lambda: os.chown("dangling", -1, -1, dir_fd=top)),
          m(lambda: os.chown("missing", -1, -1, dir_fd=top)), m(lambda: os.chown("f", -1, -1, dir_fd=fd)), m(lambda: os.chown("f", -1, -1, dir_fd=987)), m(lambda: os.chown(os.path.join(d, "f"), -1, -1, dir_fd=fd)),
          m(lambda: os.chown("f", -1, -1)))
    os.chdir(d)
    print("chown refuses:", m(lambda: os.chown("missing", -1, -1)), m(lambda: os.chown(b"missing", -1, -1)), m(lambda: os.chown(987, -1, -1)), m(lambda: os.chown(fd, -1, -1, follow_symlinks=False)), m(lambda: os.chown(fd, -1, -1, dir_fd=top)),
          m(lambda: os.chown("f", -1)), m(lambda: os.chown("f")), m(lambda: os.chown("f", -1, -1, top)), m(lambda: os.chown(1.5, -1, -1)), m(lambda: os.chown("f", -1, -1, dir_fd="x")), m(lambda: os.chown("f", -1, -1, follow=True)))  # type: ignore[call-arg, arg-type]
    print("an id:", m(lambda: os.chown("f", "x", -1)), m(lambda: os.chown("f", -1, "x")), m(lambda: os.chown("f", 1.5, -1)), m(lambda: os.chown("f", None, -1)), m(lambda: os.chown("f", -2, -1)), m(lambda: os.chown("f", -1, -2)),  # type: ignore[arg-type]
          m(lambda: os.chown("f", 2 ** 32, -1)), m(lambda: os.chown("f", -1, 2 ** 32)), m(lambda: os.chown("f", 2 ** 63, -1)), m(lambda: os.chown("f", 2 ** 64 - 1, -1)), m(lambda: os.chown("f", 2 ** 64, -1)), m(lambda: os.chown("f", -(2 ** 63) - 1, -1)),
          m(lambda: os.chown("f", -1, -(2 ** 70))), m(lambda: os.chown("f", True, True) if uid == 1 == gid else None))
    print("fchown:", m(lambda: os.fchown(fd, uid, gid)), m(lambda: os.fchown(fd, -1, -1)), m(lambda: os.fchown(fd=fd, uid=-1, gid=gid)), m(lambda: os.fchown(987, -1, -1)), m(lambda: os.fchown(fd, -1)), m(lambda: os.fchown("f", -1, -1)),  # type: ignore[call-arg, arg-type]
          m(lambda: os.fchown(fd, "x", -1)), m(lambda: os.fchown(fd, -2, -1)), m(lambda: os.fchown(fd, -1, 2 ** 64)), m(lambda: os.fchown(1.5, -1, -1)), owner("f"))  # type: ignore[arg-type]
    print("lchown:", m(lambda: os.lchown("dangling", uid, gid)), m(lambda: os.lchown("ln", -1, -1)), m(lambda: os.lchown(path=b"f", uid=uid, gid=-1)), m(lambda: os.lchown("missing", -1, -1)), m(lambda: os.lchown("f", -1)),  # type: ignore[call-arg]
          m(lambda: os.lchown(fd, -1, -1)), m(lambda: os.lchown("f", -2, -1)), m(lambda: os.lchown("f", -1, "x")), m(lambda: os.lchown("f", -1, -1, follow_symlinks=False)), owner("dangling", False))  # type: ignore[arg-type, call-arg]

    # who the process is
    three = os.getresuid()
    groups = os.getgroups()
    print("ids:", type(three).__name__, len(three), three[0] == os.getuid(), three[1] == os.geteuid(), all(type(v) is int for v in three), os.getresgid()[0] == os.getgid(), os.getresgid()[1] == os.getegid(), len(os.getresgid()),
          type(groups).__name__, all(type(g) is int and g >= 0 for g in groups), m(lambda: os.getresuid(1)), m(lambda: os.getresgid(x=1)), m(lambda: os.getgroups(1)))  # type: ignore[call-arg]
    print("group and session:", os.getpgid(0) == os.getpgrp(), os.getpgid(os.getpid()) == os.getpgrp(), os.getpgid(pid=0) == os.getpgrp(), type(os.getpgrp()).__name__, os.getsid(0) == os.getsid(os.getpid()), type(os.getsid(0)).__name__,
          os.getpgid(Index(0)) == os.getpgrp(), m(lambda: os.getpgid(NO_PROCESS)), m(lambda: os.getsid(NO_PROCESS)), m(lambda: os.getpgid("x")), m(lambda: os.getpgid()), m(lambda: os.getpgid(2 ** 40)), m(lambda: os.getsid(pid=0)),  # type: ignore[arg-type, call-arg]
          m(lambda: os.getsid()), m(lambda: os.getsid(1.5)), m(lambda: os.getpgrp(1)))  # type: ignore[call-arg, arg-type]
    print("priority:", os.getpriority(os.PRIO_PROCESS, 0) == os.nice(0), os.getpriority(which=os.PRIO_PROCESS, who=os.getpid()) == os.nice(0), type(os.nice(0)).__name__, type(os.getpriority(os.PRIO_PGRP, 0)).__name__,
          type(os.getpriority(os.PRIO_USER, os.getuid())).__name__, m(lambda: os.getpriority(99, 0)), m(lambda: os.getpriority(os.PRIO_PROCESS, NO_PROCESS)), m(lambda: os.getpriority(os.PRIO_PROCESS)), m(lambda: os.getpriority("x", 0)),  # type: ignore[call-arg, arg-type]
          m(lambda: os.nice("x")), m(lambda: os.nice()), m(lambda: os.nice(increment=0)), m(lambda: os.nice(2 ** 40)), (os.PRIO_PROCESS, os.PRIO_PGRP, os.PRIO_USER))  # type: ignore[arg-type, call-arg]

    # the load, a yield, and random bytes from the kernel
    load = os.getloadavg()
    one, two = os.getrandom(16), os.getrandom(16)
    print("load:", type(load).__name__, len(load), all(type(v) is float and v >= 0.0 for v in load), m(lambda: os.getloadavg(1)), "yield:", os.sched_yield(), m(lambda: os.sched_yield(1)))  # type: ignore[call-arg, func-returns-value]
    print("getrandom:", type(one).__name__, len(one), one != two, os.getrandom(0), len(os.getrandom(size=4, flags=os.GRND_NONBLOCK)), len(os.getrandom(3, os.GRND_RANDOM)), len(os.getrandom(Index(5))), m(lambda: os.getrandom(-1)),  # type: ignore[arg-type]
          m(lambda: os.getrandom(4, 99999)), m(lambda: os.getrandom("x")), m(lambda: os.getrandom()), m(lambda: os.getrandom(1, 2, 3)), m(lambda: os.getrandom(2 ** 70)), m(lambda: os.getrandom(1, "x")), m(lambda: os.getrandom(1, flag=0)),  # type: ignore[arg-type, call-arg]
          (os.GRND_NONBLOCK, os.GRND_RANDOM))

    os.close(fd)
    os.close(top)
    os.chdir("/")
    for name in ("f", "ln", "dangling"):
        os.unlink(os.path.join(d, name))
    os.rmdir(d)


if __name__ == "__main__":
    main()
