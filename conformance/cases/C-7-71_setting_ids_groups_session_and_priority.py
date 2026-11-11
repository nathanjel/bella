# clause: C-7-71
# spec: section 7
# status: P1
# source: dialect specification section 7 (os), Modules/posixmodule.c (os_setuid_impl, os_seteuid_impl, os_setgid_impl, os_setegid_impl, os_setreuid_impl, os_setregid_impl, os_setresuid_impl, os_setresgid_impl, os_setgroups, os_initgroups_impl, os_setpgid_impl, os_setpgrp_impl, os_setsid_impl, os_setpriority_impl, _Py_Uid_Converter, _Py_Gid_Converter)
"""Setting what the process is: its user and group ids (setuid, seteuid, setgid, setegid, setreuid, setregid, setresuid,
setresgid), its groups (setgroups, initgroups), its process group and session (setpgid, setpgrp, setsid) and its priority
(setpriority). What each takes, what it refuses before the system is asked, and what its OSError carries."""
# ruff: noqa: E501
# What a process may set depends on who runs it. The case sets each id to what it already is, which anyone may, asks for what
# nobody may, and says of the process group and the session what follows from the process being a leader or not.
import os
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


class Groups:
    """A sequence by its two methods, which is all setgroups asks."""

    def __init__(self, *items: object) -> None:
        self.items = items

    def __len__(self) -> int:
        return len(self.items)

    def __getitem__(self, i: int) -> object:
        return self.items[i]


REFUSED = "PermissionError: (1, 'Operation not permitted', None)"


def main() -> None:
    u, g = os.getuid(), os.getgid()
    before = (os.getresuid(), os.getresgid(), os.getgroups())

    # an id is set to itself, or left alone with -1 where two or three are given at once
    print("user ids:", os.setuid(u), os.seteuid(u), os.setuid(Index(u)), os.setreuid(u, u), os.setreuid(-1, -1), os.setreuid(u, -1), os.setreuid(-1, Index(u)), os.setresuid(u, u, u), os.setresuid(-1, -1, -1),  # type: ignore[func-returns-value, arg-type]
          os.setresuid(-1, u, -1), os.getresuid() == before[0])  # type: ignore[func-returns-value]
    print("group ids:", os.setgid(g), os.setegid(g), os.setgid(Index(g)), os.setregid(g, g), os.setregid(-1, -1), os.setregid(-1, g), os.setresgid(g, g, g), os.setresgid(-1, -1, -1), os.setresgid(g, -1, -1),  # type: ignore[func-returns-value, arg-type]
          os.getresgid() == before[1], os.getgroups() == before[2])
    print("ids refused:", m(lambda: os.setuid(-1)), m(lambda: os.seteuid(-1)), m(lambda: os.setgid(-1)), m(lambda: os.setegid(-1)), m(lambda: os.setuid(2**32)), m(lambda: os.setuid(-2)), m(lambda: os.setuid(2**70)), m(lambda: os.setuid("x")),  # type: ignore[arg-type]
          m(lambda: os.setuid(1.5)), m(lambda: os.setuid()), m(lambda: os.setuid(u, u)), m(lambda: os.setuid(uid=u)), m(lambda: os.seteuid("x")), m(lambda: os.seteuid()), m(lambda: os.seteuid(2**32)), m(lambda: os.setgid("x")),  # type: ignore[arg-type, call-arg]
          m(lambda: os.setgid()), m(lambda: os.setgid(2**32)), m(lambda: os.setegid(None)), m(lambda: os.setegid()), m(lambda: os.setreuid(u)), m(lambda: os.setreuid("x", u)), m(lambda: os.setreuid(u, "x")),  # type: ignore[call-arg, arg-type]
          m(lambda: os.setreuid(ruid=u, euid=u)), m(lambda: os.setreuid(2**32, u)), m(lambda: os.setreuid(-2, -2)), m(lambda: os.setreuid(u, u, u)), m(lambda: os.setregid(g)), m(lambda: os.setregid("x", g)),  # type: ignore[call-arg, arg-type]
          m(lambda: os.setregid(g, 1.5)), m(lambda: os.setresuid(u, u)), m(lambda: os.setresuid("x", u, u)), m(lambda: os.setresuid(u, u, "x")), m(lambda: os.setresuid(u, u, u, u)), m(lambda: os.setresuid(ruid=u, euid=u, suid=u)),  # type: ignore[arg-type, call-arg]
          m(lambda: os.setresuid(-2, u, u)), m(lambda: os.setresgid(g, g)), m(lambda: os.setresgid(g, "x", g)), m(lambda: os.setresgid(g, g, 2**32)), (os.getresuid(), os.getresgid(), os.getgroups()) == before)  # type: ignore[call-arg, arg-type]

    # the groups: what is refused before the system is asked (whether it then allows it is the caller's privilege)
    print("setgroups refuses:", m(lambda: os.setgroups(5)), m(lambda: os.setgroups(["x"])), m(lambda: os.setgroups([2**32])), m(lambda: os.setgroups([-2])), m(lambda: os.setgroups()), m(lambda: os.setgroups([g], 1)),  # type: ignore[arg-type, list-item, call-arg]
          m(lambda: os.setgroups(groups=[g])), m(lambda: os.setgroups(iter([g]))), m(lambda: os.setgroups("abc")), m(lambda: os.setgroups(range(70000))), m(lambda: os.setgroups({g: 1})), m(lambda: os.setgroups([1.5])),  # type: ignore[call-arg, arg-type, list-item]
          m(lambda: os.setgroups([g, "x"])), m(lambda: os.setgroups({g})), m(lambda: os.setgroups(Groups(g, None))), m(lambda: os.setgroups(Groups(2**70))), m(lambda: os.initgroups("root")), m(lambda: os.initgroups(5, 0)),  # type: ignore[list-item, arg-type, call-arg]
          m(lambda: os.initgroups("root", "x")), m(lambda: os.initgroups("a\0b", 0)), m(lambda: os.initgroups(username="root", gid=0)), m(lambda: os.initgroups("root", 2**32)), m(lambda: os.initgroups("root", 0, 0)),  # type: ignore[arg-type, call-arg]
          os.getgroups() == before[2])

    # the session and the process group. A group's leader cannot start a session; a session's leader cannot change its group.
    leads_group = os.getpgrp() == os.getpid()
    print("setsid:", m(lambda: os.setsid()) == (REFUSED if leads_group else "None"), os.getsid(0) == os.getpid() or leads_group, m(lambda: os.setsid(1)), m(lambda: os.setsid(x=1)))  # type: ignore[call-arg]
    leads_session = os.getsid(0) == os.getpid()
    print("setpgrp and setpgid:", m(lambda: os.setpgrp()) == (REFUSED if leads_session else "None"), os.getpgrp() == os.getpid(), m(lambda: os.setpgid(0, os.getpgrp())) == (REFUSED if leads_session else "None"),
          m(lambda: os.setpgid(os.getpid(), 0)) == (REFUSED if leads_session else "None"), m(lambda: os.setpgid(Index(0), Index(0))) == (REFUSED if leads_session else "None"), os.getpgid(0) == os.getpid(),  # type: ignore[arg-type]
          m(lambda: os.setpgid(2**30, 0)), m(lambda: os.setpgid(0, -1)), m(lambda: os.setpgid(0, 2**30)), m(lambda: os.setpgid(0)), m(lambda: os.setpgid("x", 0)), m(lambda: os.setpgid(0, "x")), m(lambda: os.setpgid(pid=0, pgrp=0)),  # type: ignore[call-arg, arg-type]
          m(lambda: os.setpgid(0, 0, 0)), m(lambda: os.setpgid(2**40, 0)), m(lambda: os.setpgid(-1, 0)), m(lambda: os.setpgrp(1)), m(lambda: os.setpgrp(x=1)))  # type: ignore[call-arg]

    # the priority: set to what it is; lower needs a privilege, and higher cannot be taken back
    nice = os.getpriority(os.PRIO_PROCESS, 0)
    print("setpriority:", os.setpriority(os.PRIO_PROCESS, 0, nice), os.setpriority(which=os.PRIO_PROCESS, who=os.getpid(), priority=nice), os.setpriority(os.PRIO_PGRP, 0, Index(nice)), os.getpriority(os.PRIO_PROCESS, 0) == nice,  # type: ignore[func-returns-value, arg-type]
          m(lambda: os.setpriority(os.PRIO_PGRP, 2**30, nice)), m(lambda: os.setpriority(99, 0, nice)), m(lambda: os.setpriority(os.PRIO_PROCESS, 0)), m(lambda: os.setpriority("x", 0, 0)), m(lambda: os.setpriority(0, "x", 0)),  # type: ignore[call-arg, arg-type]
          m(lambda: os.setpriority(0, 0, "x")), m(lambda: os.setpriority(0, 0, 0, 0)), m(lambda: os.setpriority(0, 0, priorit=0)), m(lambda: os.setpriority(0, 0, 2**40)), m(lambda: os.setpriority(os.PRIO_PROCESS, 2**30, nice)),  # type: ignore[arg-type, call-arg]
          m(lambda: os.setpriority(os.PRIO_USER, 2**31 - 1, nice)), m(lambda: os.setpriority(0, 2**31, nice)), m(lambda: os.setpriority(1.5, 0, 0)), os.getpriority(os.PRIO_PROCESS, 0) == nice, (os.PRIO_PROCESS, os.PRIO_PGRP, os.PRIO_USER))  # type: ignore[arg-type]


if __name__ == "__main__":
    main()
