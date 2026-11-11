# clause: C-7-74
# spec: section 7
# status: P1
# source: dialect specification section 7 (os), Modules/posixmodule.c (py_posix_spawn, parse_file_actions, parse_posix_spawn_flags, parse_arglist, parse_envlist, os_wait_impl, os_waitpid_impl, os_waitid_impl, os_system_impl, os_execv_impl, os_execve_impl), Python/pylifecycle.c (signal_install_handlers: what a child inherits)
"""Starting a program and waiting for it: posix_spawn and posix_spawnp with their file actions and flags, wait, waitpid and
waitid and what a status says, os.system, and execv and execve, which replace the program. What each refuses, and what its
OSError carries. The case ends as a shell, which prints its last line."""
# ruff: noqa: E501, PTH, S605, S606, S607
# The children are /bin/sh with a script. A child that must still be running waits on a pipe the case holds, not on a clock.
import os
import sys
import tempfile
from collections.abc import Callable, Mapping

SH = "/bin/sh"


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


def spawn(script: str, env: Mapping[str, str] | None = None, **options: object) -> int:
    return os.posix_spawn(SH, ["sh", "-c", script], {} if env is None else env, **options)  # type: ignore[arg-type]


def reap(pid: int) -> tuple[bool, int, int]:
    """Whose status came, the status, and what it says: an exit code, or a signal's number negated."""
    got = os.waitpid(pid, 0)
    return got[0] == pid, got[1], os.waitstatus_to_exitcode(got[1])


def refused(argv: object = ("sh", "-c", "exit 0"), env: object = None, path: object = SH, **options: object) -> str:
    """What posix_spawn says to arguments it should not take; a child that starts all the same is waited for."""
    try:
        pid = os.posix_spawn(path, argv, {} if env is None else env, **options)  # type: ignore[arg-type]
    except OSError as e:
        return type(e).__name__ + ": " + repr((e.errno, e.strerror, e.filename))
    except Exception as e:
        return type(e).__name__
    os.waitpid(pid, 0)
    return "started"


def main() -> None:
    d = tempfile.mkdtemp()
    out = os.path.join(d, "out")
    os.environ["BELLA_CASE_WORD"] = "from the program's own environment"

    print("spawn and waitpid:", reap(spawn("exit 7")), reap(spawn("kill -9 $$")), reap(spawn('exit "$CODE"', {"CODE": "5"})), reap(os.posix_spawnp("sh", ["sh", "-c", "exit 3"], {"PATH": "/bin:/usr/bin"})),
          reap(os.posix_spawn(os.fsencode(SH), (b"sh", "-c", "exit 2"), {b"A": b"b"})), type(spawn("exit 0")).__name__, os.wait()[1])
    print("no children:", m(os.wait), m(lambda: os.waitpid(-1, 0)), m(lambda: os.waitpid(2**30, 0)), m(lambda: os.waitid(os.P_ALL, 0, os.WEXITED)), m(lambda: os.waitpid(0, os.WNOHANG)), m(lambda: os.waitid(os.P_PID, 2**30, os.WEXITED | os.WNOHANG)))

    # a child that waits on a pipe is still running: nothing to report yet
    r, w = os.pipe()
    pid = spawn("read line", file_actions=[(os.POSIX_SPAWN_DUP2, r, 0), (os.POSIX_SPAWN_CLOSE, w)])
    print("still running:", os.waitpid(pid, os.WNOHANG), os.waitid(os.P_PID, pid, os.WEXITED | os.WNOHANG), os.waitpid(Index(pid), Index(os.WNOHANG)), os.close(w), reap(pid), m(lambda: os.waitpid(pid, 0)))  # type: ignore[func-returns-value, arg-type]
    os.close(r)

    # waitid says who, why and how; with WNOWAIT the child is left to be waited for again
    pid = spawn("exit 4")
    got = os.waitid(os.P_PID, pid, os.WEXITED | os.WNOWAIT)
    assert got is not None
    again = os.wait()
    pid2 = spawn("kill -15 $$")
    killed = os.waitid(os.P_ALL, 0, os.WEXITED)
    assert killed is not None
    print("waitid:", type(got).__name__, type(got).__module__, len(got), got.si_pid == pid, got.si_uid == os.getuid(), got.si_signo, got.si_status, got.si_code == os.CLD_EXITED, again == (pid, 4 << 8),
          killed.si_pid == pid2, killed.si_status, killed.si_code == os.CLD_KILLED, (os.P_PID, os.P_PGID, os.P_ALL, os.WEXITED, os.WNOWAIT, os.WNOHANG, os.CLD_EXITED, os.CLD_KILLED))
    print("the wait family refuses:", m(lambda: os.wait(1)), m(lambda: os.waitpid(0)), m(lambda: os.waitpid("x", 0)), m(lambda: os.waitpid(0, "x")), m(lambda: os.waitpid(pid=0, options=0)), m(lambda: os.waitpid(2**40, 0)),  # type: ignore[arg-type, call-arg]
          m(lambda: os.waitpid(0, 0, 0)), m(lambda: os.waitpid(-1, 2**20)), m(lambda: os.waitid(os.P_ALL, 0)), m(lambda: os.waitid("x", 0, os.WEXITED)), m(lambda: os.waitid(os.P_PID, "x", os.WEXITED)), m(lambda: os.waitid(os.P_ALL, 0, 0)),  # type: ignore[arg-type, call-arg]
          m(lambda: os.waitid(99, 0, os.WEXITED)), m(lambda: os.waitid(os.P_PID, -1, os.WEXITED)), m(lambda: os.waitid(idtype=os.P_ALL, id=0, options=os.WEXITED)), m(lambda: os.waitid(os.P_PID, 2**40, os.WEXITED)))  # type: ignore[call-arg]

    # file actions: what the child's descriptors are; and the child's world: this program's directory, and its environment if none is given
    os.chdir(d)
    pid = spawn("echo to a file; echo $0 and $1", file_actions=((os.POSIX_SPAWN_OPEN, 1, out, os.O_WRONLY | os.O_CREAT, 0o600),))
    first = reap(pid)
    with open(out) as f:
        written = f.read()
    r, w = os.pipe()
    pid = os.posix_spawn(SH, ["sh", "-c", 'echo "$BELLA_CASE_WORD"; echo "${CODE-unset}"; test "$(pwd -P)" = "$1" && echo here; kill -PIPE $$; echo "a signal the program ignores is ignored"', "sh", os.path.realpath(d)], None,
                         file_actions=[(os.POSIX_SPAWN_DUP2, w, 1), (os.POSIX_SPAWN_CLOSE, r)])
    os.close(w)
    second = reap(pid)
    told = os.read(r, 1000)
    os.close(r)
    print("file actions and the child's world:", first, repr(written), second, told, reap(spawn("kill -PIPE $$; exit 3", setsigdef=[13])), os.path.getsize(out))
    os.chdir("/")

    print("the flags:", reap(spawn("exit 1", setpgroup=0)), reap(spawn("exit 2", resetids=True)), reap(spawn("exit 4", setsigmask=[2, 15])), reap(spawn("exit 5", setsigdef={2})), reap(spawn("exit 6", scheduler=(None, os.sched_param(0)))),
          reap(spawn("exit 7", scheduler=(os.SCHED_OTHER, os.sched_param(0)))), reap(spawn("exit 8", file_actions=())), reap(spawn("exit 9", file_actions=None, setpgroup=None, scheduler=None, setsid=False)),
          reap(spawn("exit 10", resetids="yes", setsid=0)), m(lambda: spawn("exit 3", setsid=True)), (os.POSIX_SPAWN_OPEN, os.POSIX_SPAWN_CLOSE, os.POSIX_SPAWN_DUP2))
    print("spawn refuses:", refused(path="/no/such/program") == "FileNotFoundError: " + repr((2, "No such file or directory", "/no/such/program")), refused(path=d) == "PermissionError: " + repr((13, "Permission denied", d)),
          refused(argv=[]), refused(argv=[""]), refused(argv="abc"), refused(argv=iter(["sh"])), refused(argv=["sh", 5]), refused(argv=["sh\0"]), refused(path=5), refused(path="a\0b"), refused(env=5), refused(env=[("A", "b")]),
          refused(env={"A=B": "c"}), refused(env={"": "c"}), refused(env={"A": 5}), refused(env={"A": "b\0"}), refused(env={"=A": "c"}), refused(file_actions=5), refused(file_actions=[5]), refused(file_actions=[()]), refused(file_actions=[(99,)]),
          refused(file_actions=[("x",)]), refused(file_actions=[(os.POSIX_SPAWN_CLOSE,)]), refused(file_actions=[(os.POSIX_SPAWN_CLOSE, "x")]), refused(file_actions=[(os.POSIX_SPAWN_CLOSE, -1)]), refused(file_actions=[(os.POSIX_SPAWN_CLOSE, 987)]),
          refused(file_actions=[(os.POSIX_SPAWN_DUP2, 1)]), refused(file_actions=[(os.POSIX_SPAWN_DUP2, 987, 1)]) == "OSError: " + repr((9, "Bad file descriptor", SH)), refused(file_actions=[(os.POSIX_SPAWN_OPEN, 1, out)]),
          refused(file_actions=[(os.POSIX_SPAWN_OPEN, 1, 5, 0, 0)]), refused(file_actions=[(os.POSIX_SPAWN_OPEN, 1, out, 0, "x")]), refused(file_actions=[(os.POSIX_SPAWN_CLOSE, -1), (99,)]), refused(file_actions=[(99,), (os.POSIX_SPAWN_CLOSE, -1)]),
          refused(setpgroup="x"), refused(setpgroup=2**40), refused(setpgroup=2**30) == "PermissionError: " + repr((1, "Operation not permitted", SH)), refused(setsigmask=5), refused(setsigmask=[9999]), refused(setsigmask=[0]), refused(setsigmask=["x"]),
          refused(setsigdef=[65]), refused(scheduler=5), refused(scheduler=(1,)), refused(scheduler=(None, 5)), refused(scheduler=(99, os.sched_param(0))), refused(scheduler=("x", os.sched_param(0))), refused(scheduler=(None, os.sched_param("x"))),  # type: ignore[arg-type]
          refused(nope=1), m(lambda: os.posix_spawn(SH, ["sh"])), m(lambda: os.posix_spawn(SH, ["sh"], {}, ())), m(lambda: os.posix_spawnp("no-such-program-here", ["x"], {"PATH": "/bin"})), m(lambda: os.posix_spawnp("sh", [], {})))  # type: ignore[call-arg]

    # os.system: the shell's status, as wait gives it
    sys.stdout.flush()
    print("system:", os.system("exit 3"), os.system("echo from the shell"), os.system(b"true"), os.system(command="kill -9 $$"), os.system(""), os.system("no-such-command-here 2>/dev/null"), os.waitstatus_to_exitcode(os.system("exit 200")),
          os.system('test "$BELLA_CASE_WORD" = "from the program\'s own environment"'), os.system("kill -PIPE $$; exit 4"), m(lambda: os.system(5)), m(lambda: os.system()), m(lambda: os.system("a\0b")), m(lambda: os.system("true", 1)),  # type: ignore[arg-type, call-arg]
          m(lambda: os.system(comman="true")))  # type: ignore[call-arg]

    # exec that fails leaves the program as it was
    print("exec refuses:", m(lambda: os.execv("/no/such/program", ["x"])), m(lambda: os.execv(d, ["x"])), m(lambda: os.execv(SH, [])), m(lambda: os.execv(SH, [""])), m(lambda: os.execv(SH, "abc")), m(lambda: os.execv(SH, ["sh", 5])),  # type: ignore[arg-type]
          m(lambda: os.execv(SH)), m(lambda: os.execv(5, ["x"])), m(lambda: os.execv(path=SH, argv=["x"])), m(lambda: os.execv(SH, ["sh\0x"])), m(lambda: os.execve("/no/such/program", ["x"], {})) == "FileNotFoundError: " + repr((2, "No such file or directory", "/no/such/program")),  # type: ignore[call-arg, arg-type]
          m(lambda: os.execve(SH, ["sh"], 5)), m(lambda: os.execve(SH, [], {})), m(lambda: os.execve(SH, [""], {})), m(lambda: os.execve(SH, "abc", {})), m(lambda: os.execve(SH, ["sh"], {"A=B": "c"})), m(lambda: os.execve(SH, ["sh"])),  # type: ignore[arg-type, call-arg]
          m(lambda: os.execve(987, ["sh"], {})), m(lambda: os.execve(d, ["x"], {})) == "PermissionError: " + repr((13, "Permission denied", d)), m(lambda: os.execve(SH, ["sh"], {"A": "b\0"})), m(lambda: os.execve(SH, ["sh"], {"": "b"})))

    os.unlink(out)
    os.rmdir(d)
    print("the program ends here, and the shell says the rest")
    sys.stdout.flush()
    os.execve(SH, ["sh", "-c", 'echo "the last line, from the shell: $WORD, $0"', "argv0"], {"WORD": "passed on"})


if __name__ == "__main__":
    main()
