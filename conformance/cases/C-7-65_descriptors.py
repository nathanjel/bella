# clause: C-7-65
# spec: section 7
# status: P1
# source: dialect specification section 7 (os), Modules/posixmodule.c (os_dup_impl, os_dup2_impl, os_pipe_impl, os_pipe2_impl, os_get_inheritable_impl, os_set_inheritable_impl, os_get_blocking_impl, os_set_blocking_impl, os_closerange_impl, os_fchdir_impl, os_fdatasync_impl, os_sync_impl, os_truncate_impl, os_ftruncate_impl, os_pread_impl, os_pwrite_impl, os_lockf_impl, os_posix_fallocate_impl, os_posix_fadvise_impl), Python/fileutils.c (_Py_dup, _Py_set_inheritable, _Py_set_blocking)
"""The functions of os that work on a descriptor: dup and dup2 (a new descriptor is not inherited unless asked), pipe and pipe2,
whether a descriptor is inherited and whether it blocks, closerange, fchdir, fdatasync and sync, truncate and ftruncate, pread
and pwrite (which leave the position alone), lockf, posix_fallocate and posix_fadvise; what each takes by position only, and
what an OSError from each carries."""
# ruff: noqa: E501, PTH
# A descriptor's number is the process's own: what is printed about one is how it relates to another. A number that was closed
# is given out again by the next open, so the descriptor that is not open is a number far above any the program is given.
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


def gone(fd: int) -> bool:
    try:
        os.fstat(fd)
    except OSError:
        return True
    return False


class Fileno:
    def __init__(self, fd: int) -> None:
        self.fd = fd

    def fileno(self) -> int:
        return self.fd


def size(name: str) -> int:
    return os.stat(name).st_size


def main() -> None:
    d = tempfile.mkdtemp()
    os.chdir(d)
    with open("f", "wb") as f:
        f.write(b"0123456789")
    fd = os.open("f", os.O_RDWR)
    readonly = os.open("f", os.O_RDONLY)
    top = os.open(d, os.O_RDONLY)
    closed = 987
    print("not open:", gone(closed))

    # dup: the same open file under a new number, not inherited
    again = os.dup(fd)
    os.lseek(fd, 3, os.SEEK_SET)
    print("dup:", type(again).__name__, again != fd, again > 2, os.get_inheritable(again), os.fstat(again).st_ino == os.fstat(fd).st_ino, os.lseek(again, 0, os.SEEK_CUR), os.read(again, 2), os.lseek(fd, 0, os.SEEK_CUR))
    os.close(again)
    print("dup refuses:", m(lambda: os.dup(closed)), m(lambda: os.dup(-1)), m(lambda: os.dup("f")), m(lambda: os.dup(1.5)), m(lambda: os.dup(2 ** 40)), m(lambda: os.dup()), m(lambda: os.dup(fd, 1)), m(lambda: os.dup(fd=fd)))  # type: ignore[arg-type, call-arg]

    # dup2: onto a number the program holds; inherited unless told otherwise
    target = os.open("f", os.O_RDONLY)
    other = os.open("f", os.O_RDONLY)
    print("dup2:", os.dup2(fd, target) == target, os.get_inheritable(target), os.dup2(fd, other, False) == other, os.get_inheritable(other), os.dup2(fd=fd, fd2=target, inheritable=False) == target, os.get_inheritable(target),
          os.dup2(fd, target, inheritable=1) == target, os.get_inheritable(target), os.lseek(target, 0, os.SEEK_CUR) == os.lseek(fd, 0, os.SEEK_CUR), os.dup2(fd, fd) == fd, m(lambda: os.dup2(fd, fd, inheritable=False)))  # type: ignore[arg-type]
    print("dup2 refuses:", m(lambda: os.dup2(closed, target)), m(lambda: os.dup2(fd, -1)), m(lambda: os.dup2(fd)), m(lambda: os.dup2("f", target)), m(lambda: os.dup2(fd, target, True, 1)), m(lambda: os.dup2(fd, target, inherit=True)),  # type: ignore[call-arg, arg-type]
          m(lambda: os.dup2(fd, 2 ** 40)))
    os.close(target)
    os.close(other)

    # pipe and pipe2
    r, w = os.pipe()
    print("pipe:", type(r).__name__, type(w).__name__, r != w, os.get_inheritable(r), os.get_inheritable(w), os.get_blocking(r), os.write(w, b"abc"), os.read(r, 10), os.close(w), os.read(r, 10), os.close(r), m(lambda: os.pipe(1)), m(lambda: os.pipe(x=1)))  # type: ignore[call-arg, func-returns-value]
    r, w = os.pipe2(0)
    print("pipe2(0):", os.get_inheritable(r), os.get_inheritable(w), os.get_blocking(r))
    os.close(r)
    os.close(w)
    r, w = os.pipe2(os.O_CLOEXEC | os.O_NONBLOCK)
    print("pipe2(O_CLOEXEC | O_NONBLOCK):", os.get_inheritable(r), os.get_inheritable(w), os.get_blocking(r), os.get_blocking(w), m(lambda: os.read(r, 1)))
    print("pipe2 refuses:", m(lambda: os.pipe2()), m(lambda: os.pipe2("x")), m(lambda: os.pipe2(flags=0)), m(lambda: os.pipe2(-1)), m(lambda: os.pipe2(0, 0)), m(lambda: os.pipe2(2 ** 40)))  # type: ignore[call-arg, arg-type]

    # inherited or not, blocking or not
    print("inheritable:", os.get_inheritable(fd), os.set_inheritable(fd, True), os.get_inheritable(fd), os.set_inheritable(fd, 0), os.get_inheritable(fd), os.set_inheritable(fd, 5), os.get_inheritable(fd), os.set_inheritable(fd, False),  # type: ignore[func-returns-value, arg-type]
          m(lambda: os.set_inheritable(fd, "x")), m(lambda: os.set_inheritable(fd, 1.5)), m(lambda: os.set_inheritable(closed, True)), m(lambda: os.get_inheritable(closed)), m(lambda: os.get_inheritable("f")),  # type: ignore[arg-type]
          m(lambda: os.get_inheritable(fd=fd)), m(lambda: os.set_inheritable(fd)), m(lambda: os.set_inheritable(fd, inheritable=True)), m(lambda: os.get_inheritable()))  # type: ignore[call-arg]
    print("blocking:", os.set_blocking(r, True), os.get_blocking(r), os.set_blocking(r, False), os.get_blocking(r), os.set_blocking(r, [1]), os.get_blocking(r), os.set_blocking(r, ""), os.get_blocking(r),  # type: ignore[func-returns-value, arg-type]
          os.get_blocking(fd), os.set_blocking(fd, False), os.get_blocking(fd), os.set_blocking(fd, True), m(lambda: os.set_blocking(closed, True)), m(lambda: os.get_blocking(closed)), m(lambda: os.get_blocking("f")),  # type: ignore[func-returns-value, arg-type]
          m(lambda: os.set_blocking(r)), m(lambda: os.set_blocking(fd=r, blocking=True)), m(lambda: os.get_blocking(fd=r)))  # type: ignore[call-arg]

    # closerange: up to, not including, the second; nothing if there is nothing between; no error for what is not open
    a = os.dup(fd)
    b = os.dup(fd)
    print("closerange:", os.closerange(a, a + 1), gone(a), gone(b), os.closerange(b, b), gone(b), os.closerange(b, b - 5), gone(b), os.closerange(b, b + 1), gone(b), os.closerange(closed, closed + 1),  # type: ignore[func-returns-value]
          m(lambda: os.closerange(a)), m(lambda: os.closerange("a", 1)), m(lambda: os.closerange(fd_low=1, fd_high=1)), m(lambda: os.closerange(1, 2 ** 40)))  # type: ignore[call-arg, arg-type]

    # fchdir, fdatasync, sync
    os.mkdir("sub")
    under = os.open("sub", os.O_RDONLY)
    print("fchdir:", os.fchdir(under), os.path.basename(os.getcwd()), os.fchdir(fd=top), os.getcwd() == os.path.realpath(d), os.fchdir(Fileno(under)), os.path.basename(os.getcwd()), os.fchdir(top),  # type: ignore[func-returns-value]
          m(lambda: os.fchdir(fd)), m(lambda: os.fchdir(closed)), m(lambda: os.fchdir("sub")), m(lambda: os.fchdir()), m(lambda: os.fchdir(top, 1)), m(lambda: os.fchdir(1.5)))  # type: ignore[arg-type, call-arg]
    print("fdatasync:", os.fdatasync(fd), os.fdatasync(fd=fd), os.fdatasync(Fileno(fd)), m(lambda: os.fdatasync(r)), m(lambda: os.fdatasync(closed)), m(lambda: os.fdatasync("f")), m(lambda: os.fdatasync()), os.sync(),  # type: ignore[func-returns-value, arg-type, call-arg]
          m(lambda: os.sync(1)))  # type: ignore[call-arg]

    # truncate by name or by descriptor, ftruncate
    print("truncate:", os.truncate("f", 4), size("f"), os.truncate("f", 8), size("f"), os.pread(fd, 20, 0), os.truncate(fd, 6), size("f"), os.truncate(path=b"f", length=5), size("f"), os.ftruncate(fd, 7), size("f"), os.ftruncate(fd, 0), size("f"),  # type: ignore[func-returns-value]
          os.lseek(fd, 0, os.SEEK_CUR))
    print("truncate refuses:", m(lambda: os.truncate("missing", 1)), m(lambda: os.truncate("f", -1)), m(lambda: os.truncate("sub", 0)), m(lambda: os.truncate(readonly, 1)), m(lambda: os.truncate(closed, 1)), m(lambda: os.truncate("f")),  # type: ignore[call-arg]
          m(lambda: os.truncate("f", "x")), m(lambda: os.truncate("f", 2 ** 70)), m(lambda: os.truncate(1.5, 1)), m(lambda: os.truncate("f", 1, 2)), m(lambda: os.truncate(b"missing", 1)))  # type: ignore[arg-type, call-arg]
    print("ftruncate refuses:", m(lambda: os.ftruncate(fd, -1)), m(lambda: os.ftruncate(readonly, 1)), m(lambda: os.ftruncate(closed, 1)), m(lambda: os.ftruncate(r, 1)), m(lambda: os.ftruncate("f", 1)), m(lambda: os.ftruncate(fd)),  # type: ignore[arg-type, call-arg]
          m(lambda: os.ftruncate(fd, "x")), m(lambda: os.ftruncate(fd=fd, length=1)), m(lambda: os.ftruncate(fd, 2 ** 70)), m(lambda: os.ftruncate(top, 0)))  # type: ignore[arg-type, call-arg]

    # pwrite and pread: at an offset, and the position stays
    os.write(fd, b"0123456789")
    where = os.lseek(fd, 4, os.SEEK_SET)
    print("pwrite, pread:", os.pwrite(fd, b"XY", 3), os.pwrite(fd, bytearray(b"Z"), 12), os.pread(fd, 4, 2), os.pread(fd, 100, 0), os.pread(fd, 5, 50), os.pread(fd, 0, 0), os.lseek(fd, 0, os.SEEK_CUR) == where, size("f"),
          os.pread(readonly, 3, 1), os.pwrite(fd, b"", 0))
    print("pread refuses:", m(lambda: os.pread(fd, -1, 0)), m(lambda: os.pread(fd, 1, -1)), m(lambda: os.pread(r, 1, 0)), m(lambda: os.pread(closed, 1, 0)), m(lambda: os.pread(fd, 1)), m(lambda: os.pread(fd, "x", 0)), m(lambda: os.pread(fd, 1, "x")),  # type: ignore[call-arg, arg-type]
          m(lambda: os.pread(fd=fd, length=1, offset=0)), m(lambda: os.pread(fd, 2 ** 70, 0)), m(lambda: os.pread(fd, 1, 2 ** 70)))  # type: ignore[call-arg]
    print("pwrite refuses:", m(lambda: os.pwrite(readonly, b"x", 0)), m(lambda: os.pwrite(fd, b"x", -1)), m(lambda: os.pwrite(w, b"x", 0)), m(lambda: os.pwrite(closed, b"x", 0)), m(lambda: os.pwrite(fd, "x", 0)), m(lambda: os.pwrite(fd, b"x")),  # type: ignore[arg-type, call-arg]
          m(lambda: os.pwrite(fd, b"x", "0")), m(lambda: os.pwrite(fd=fd, buffer=b"x", offset=0)), m(lambda: os.pwrite(fd, 1, 0)))  # type: ignore[arg-type, call-arg]

    # lockf: taken, asked about, tried and given up by the one process
    print("lockf:", os.lockf(fd, os.F_LOCK, 0), os.lockf(fd, os.F_TEST, 0), os.lockf(fd, os.F_TLOCK, 4), os.lockf(fd, os.F_ULOCK, 0), m(lambda: os.lockf(fd, 99, 0)), m(lambda: os.lockf(readonly, os.F_LOCK, 0)), m(lambda: os.lockf(closed, os.F_LOCK, 0)),  # type: ignore[func-returns-value]
          m(lambda: os.lockf(fd, os.F_LOCK)), m(lambda: os.lockf("f", os.F_LOCK, 0)), m(lambda: os.lockf(fd, os.F_LOCK, "x")), m(lambda: os.lockf(fd=fd, command=os.F_LOCK, length=0)), (os.F_LOCK, os.F_TLOCK, os.F_ULOCK, os.F_TEST))  # type: ignore[call-arg, arg-type]

    # posix_fallocate and posix_fadvise
    print("posix_fallocate:", os.posix_fallocate(fd, 0, 100), size("f"), os.posix_fallocate(fd, 150, 50), size("f"), os.pread(fd, 4, 0), m(lambda: os.posix_fallocate(fd, -1, 10)), m(lambda: os.posix_fallocate(fd, 0, 0)),  # type: ignore[func-returns-value]
          m(lambda: os.posix_fallocate(r, 0, 10)), m(lambda: os.posix_fallocate(readonly, 0, 10)), m(lambda: os.posix_fallocate(closed, 0, 10)), m(lambda: os.posix_fallocate(fd, 0)), m(lambda: os.posix_fallocate(fd, "x", 1)),  # type: ignore[call-arg, arg-type]
          m(lambda: os.posix_fallocate(fd=fd, offset=0, len=1)))  # type: ignore[call-arg]
    print("posix_fadvise:", os.posix_fadvise(fd, 0, 0, os.POSIX_FADV_SEQUENTIAL), os.posix_fadvise(fd, 10, 20, os.POSIX_FADV_DONTNEED), os.posix_fadvise(readonly, 0, 0, os.POSIX_FADV_NORMAL), m(lambda: os.posix_fadvise(fd, 0, 0, 99)),  # type: ignore[func-returns-value]
          m(lambda: os.posix_fadvise(r, 0, 0, os.POSIX_FADV_NORMAL)), m(lambda: os.posix_fadvise(closed, 0, 0, os.POSIX_FADV_NORMAL)), m(lambda: os.posix_fadvise(fd, 0, 0)), m(lambda: os.posix_fadvise(fd, 0, "x", 0)),  # type: ignore[call-arg, arg-type]
          m(lambda: os.posix_fadvise(fd=fd, offset=0, len=0, advice=0)),  # type: ignore[call-arg]
          (os.POSIX_FADV_NORMAL, os.POSIX_FADV_RANDOM, os.POSIX_FADV_SEQUENTIAL, os.POSIX_FADV_WILLNEED, os.POSIX_FADV_DONTNEED, os.POSIX_FADV_NOREUSE))

    for descriptor in (fd, readonly, top, under, r, w):
        os.close(descriptor)
    os.chdir("/")
    os.unlink(os.path.join(d, "f"))
    os.rmdir(os.path.join(d, "sub"))
    os.rmdir(d)


if __name__ == "__main__":
    main()
