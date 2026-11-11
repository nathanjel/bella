# clause: C-7-69
# spec: section 7
# status: P1
# source: dialect specification section 7 (os), Modules/posixmodule.c (os_readv_impl, os_preadv_impl, os_writev_impl, os_pwritev_impl, iov_setup, os_readinto_impl, os_eventfd_impl, os_eventfd_read_impl, os_eventfd_write_impl, os_memfd_create_impl, os_mkfifo_impl, os_mknod_impl, os_splice_impl)
"""Reading into buffers a program already has and writing from several at once: readv, preadv, writev, pwritev and readinto,
what counts as a sequence of buffers and what each buffer must be; and the descriptors that are made without a file: eventfd
with its counter, memfd_create; the nodes mkfifo and mknod make; splice between a pipe and a file. What each refuses, and what
its OSError carries (none of them a file name)."""
# ruff: noqa: E501, PTH
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


class Buffers:
    """A sequence by its two methods, which is all readv and writev ask."""

    def __init__(self, *items: object) -> None:
        self.items = items
        self.asked: list[int] = []

    def __len__(self) -> int:
        return len(self.items)

    def __getitem__(self, i: int) -> object:
        self.asked.append(i)
        return self.items[i]


def content(name: str) -> bytes:
    with open(name, "rb") as f:
        return f.read()


def main() -> None:
    d = tempfile.mkdtemp()
    os.chdir(d)
    with open("f", "wb") as f:
        f.write(b"0123456789abcdef")
    fd = os.open("f", os.O_RDWR)
    top = os.open(d, os.O_RDONLY)

    # readv: each buffer filled in turn, the count of what was read
    a, b, c = bytearray(4), bytearray(0), bytearray(20)
    n = os.readv(fd, [a, b, c])
    print("readv:", n, a, b, bytes(c[:12]), len(c), c[12:] == bytearray(8), os.readv(fd, [bytearray(3)]), os.readv(fd, []), os.lseek(fd, 0, 0))
    seq = Buffers(bytearray(2), bytearray(3))
    t = (bytearray(1), bytearray(1))
    print("a sequence:", os.readv(fd, seq), seq.items, seq.asked, os.readv(fd, t), t, os.readv(Index(fd), [bytearray(1)]), os.lseek(fd, 0, 1))  # type: ignore[arg-type]
    print("readv refuses:", m(lambda: os.readv(fd, 5)), m(lambda: os.readv(fd, iter([bytearray(1)]))), m(lambda: os.readv(fd, {0: bytearray(1)})), m(lambda: os.readv(fd, bytearray(2))),  # type: ignore[arg-type]
          m(lambda: os.readv(fd, [b"xx"])), m(lambda: os.readv(fd, ["xx"])), m(lambda: os.readv(fd, "xx")), m(lambda: os.readv(fd, [bytearray(1), 5])), m(lambda: os.readv(fd, [None])), m(lambda: os.readv(987, [bytearray(1)])),  # type: ignore[list-item, arg-type]
          m(lambda: os.readv(fd)), m(lambda: os.readv(fd, [bytearray(1)], 0)), m(lambda: os.readv(fd=fd, buffers=[bytearray(1)])), m(lambda: os.readv("f", [bytearray(1)])), m(lambda: os.readv(top, [bytearray(1)])),  # type: ignore[call-arg, arg-type]
          m(lambda: os.readv(fd, [bytearray(1)] * 1025)), m(lambda: os.readv(1.5, [bytearray(1)])), m(lambda: os.readv(Fileno(fd), [bytearray(1)])), os.lseek(fd, 0, 1))  # type: ignore[arg-type]

    # preadv: at an offset, the position left alone (the pinned build has no preadv2: no flags, and no offset of -1)
    p, q = bytearray(3), bytearray(3)
    os.lseek(fd, 2, 0)
    print("preadv:", os.preadv(fd, [p, q], 10), p, q, os.lseek(fd, 0, 1), os.preadv(fd, [p], 0, 0), p, os.preadv(fd, [p], 100), os.preadv(fd, [], 0), os.preadv(fd, [p], Index(1)), p, os.lseek(fd, 0, 1))  # type: ignore[arg-type]
    print("preadv refuses:", m(lambda: os.preadv(fd, [p])), m(lambda: os.preadv(fd, 5, 0)), m(lambda: os.preadv(fd, [b"x"], 0)), m(lambda: os.preadv(fd, [p], -1)), m(lambda: os.preadv(fd, [p], -2)), m(lambda: os.preadv(fd, [p], 0, 1)), m(lambda: os.preadv(fd, [p], 0, 2 ** 20)), m(lambda: os.preadv(fd, [p], "0")),  # type: ignore[arg-type, call-arg]
          m(lambda: os.preadv(fd, [p], 0, "0")), m(lambda: os.preadv(fd, [p], 2 ** 70)), m(lambda: os.preadv(fd, [p], 0, 2 ** 40)), m(lambda: os.preadv(987, [p], 0)), m(lambda: os.preadv(fd, [p], 0, 0, 0)), m(lambda: os.preadv(fd, [p], offset=0)),  # type: ignore[arg-type, call-arg]
          m(lambda: os.preadv(fd, [p], 1.5)))  # type: ignore[arg-type]

    # readinto
    os.lseek(fd, 0, 0)
    r = bytearray(6)
    print("readinto:", os.readinto(fd, r), r, os.readinto(fd, bytearray(0)), os.lseek(fd, 0, 2), os.readinto(fd, r), r, m(lambda: os.readinto(fd, b"xx")), m(lambda: os.readinto(fd, "xx")), m(lambda: os.readinto(fd, 5)),  # type: ignore[arg-type]
          m(lambda: os.readinto(987, r)), m(lambda: os.readinto(fd)), m(lambda: os.readinto(fd, r, 1)), m(lambda: os.readinto(fd=fd, buffer=r)), m(lambda: os.readinto(top, r)), m(lambda: os.readinto("f", r)))  # type: ignore[call-arg, arg-type]

    # writev and pwritev
    out = os.open("out", os.O_RDWR | os.O_CREAT, 0o600)
    print("writev:", os.writev(out, [b"ab", bytearray(b"cd"), b"", b"e"]), content("out"), os.writev(out, []), os.writev(out, (b"f",)), os.writev(out, Buffers(b"g", bytearray(b"h"))), content("out"), os.lseek(out, 0, 1),  # type: ignore[arg-type]
          os.pwritev(out, [b"XY", b"Z"], 1), content("out"), os.lseek(out, 0, 1), os.pwritev(out, [b"!"], 10, 0), content("out"), os.pwritev(out, [], 0), os.lseek(out, 0, 1))
    print("writev refuses:", m(lambda: os.writev(out, 5)), m(lambda: os.writev(out, b"ab")), m(lambda: os.writev(out, ["ab"])), m(lambda: os.writev(out, [b"a", 5])), m(lambda: os.writev(out, iter([b"a"]))), m(lambda: os.writev(987, [b"a"])),  # type: ignore[arg-type, list-item]
          m(lambda: os.writev(top, [b"a"])), m(lambda: os.writev(out)), m(lambda: os.writev(out, [b"a"], 0)), m(lambda: os.writev(fd=out, buffers=[b"a"])), m(lambda: os.writev(out, [b"a"] * 1025)), m(lambda: os.pwritev(out, [b"a"])),  # type: ignore[call-arg]
          m(lambda: os.pwritev(out, 5, 0)), m(lambda: os.pwritev(out, [b"a"], -1)), m(lambda: os.pwritev(out, [b"a"], 0, 1)), m(lambda: os.pwritev(out, [b"a"], 0, 2 ** 20)), m(lambda: os.pwritev(out, ["a"], 0)), m(lambda: os.pwritev(987, [b"a"], 0)), m(lambda: os.pwritev(out, [b"a"], "0")),  # type: ignore[arg-type, list-item]
          content("out"))

    # eventfd: a counter that a read empties, or counts down one at a time
    e = os.eventfd(3)
    first = os.eventfd_read(e)
    os.eventfd_write(e, 5)
    os.eventfd_write(e, 2)
    sem = os.eventfd(2, os.EFD_SEMAPHORE | os.EFD_NONBLOCK)
    plain = os.eventfd(0, 0)
    print("eventfd:", first, os.eventfd_read(e), os.eventfd_write(e, 1), os.eventfd_read(Fileno(e)), os.get_inheritable(e), os.get_blocking(e), os.eventfd_read(sem), os.eventfd_read(sem), m(lambda: os.eventfd_read(sem)),  # type: ignore[func-returns-value, arg-type]
          os.get_blocking(sem), os.get_inheritable(plain), os.eventfd_write(fd=plain, value=2 ** 64 - 2), os.eventfd_read(fd=plain), os.eventfd(initval=1, flags=os.EFD_CLOEXEC) > 2, os.read(os.eventfd(Index(7)), 8),  # type: ignore[func-returns-value, arg-type]
          (os.EFD_CLOEXEC, os.EFD_NONBLOCK, os.EFD_SEMAPHORE))
    print("eventfd refuses:", m(lambda: os.eventfd()), m(lambda: os.eventfd(-1)), m(lambda: os.eventfd(2 ** 32)), m(lambda: os.eventfd("1")), m(lambda: os.eventfd(1.5)), m(lambda: os.eventfd(0, 12345)), m(lambda: os.eventfd(0, "x")),  # type: ignore[call-arg, arg-type]
          m(lambda: os.eventfd(0, 0, 0)), m(lambda: os.eventfd_read(987)), m(lambda: os.eventfd_read()), m(lambda: os.eventfd_read("e")), m(lambda: os.eventfd_write(e)), m(lambda: os.eventfd_write(e, -1)),  # type: ignore[call-arg, arg-type]
          m(lambda: os.eventfd_write(e, 2 ** 64)), m(lambda: os.eventfd_write(e, 2 ** 64 - 1)), m(lambda: os.eventfd_write(e, "1")), m(lambda: os.eventfd_write(987, 1)), m(lambda: os.eventfd_write(e, 1.5)), m(lambda: os.eventfd_write(e, 1, 2)))  # type: ignore[arg-type, call-arg]

    # memfd_create: a file with a name and no directory
    mem = os.memfd_create("a name")
    os.write(mem, b"in memory")
    os.lseek(mem, 3, 0)
    print("memfd_create:", os.read(mem, 20), os.fstat(mem).st_size, stat.S_ISREG(os.fstat(mem).st_mode), os.get_inheritable(mem), os.get_inheritable(os.memfd_create("x", 0)), os.memfd_create(b"bytes") > 2,  # type: ignore[arg-type]
          os.memfd_create(name="n", flags=os.MFD_CLOEXEC) > 2, os.memfd_create("") > 2, m(lambda: os.memfd_create("a\0b")), m(lambda: os.memfd_create("n" * 250)), m(lambda: os.memfd_create("n", 2 ** 31)), m(lambda: os.memfd_create()),  # type: ignore[call-arg]
          m(lambda: os.memfd_create(5)), m(lambda: os.memfd_create("n", "x")), m(lambda: os.memfd_create("n", 0, 0)), m(lambda: os.memfd_create(None)), m(lambda: os.memfd_create("n", 1.5)),  # type: ignore[arg-type, call-arg]
          os.MFD_CLOEXEC, os.MFD_ALLOW_SEALING)

    # mkfifo and mknod
    os.mkfifo("fifo", 0o600)
    os.mkfifo(b"fifo2")
    os.mkfifo(path="fifo3", mode=0o640, dir_fd=top)
    os.mknod("node")
    os.mknod("node2", stat.S_IFREG | 0o640, 0)
    os.mknod(b"node3", mode=stat.S_IFIFO | 0o600, device=os.makedev(1, 2), dir_fd=top)
    modes = [(stat.S_IFMT(st.st_mode) == kind, stat.S_IMODE(st.st_mode) & 0o600, st.st_size) for name, kind in (("fifo", stat.S_IFIFO), ("fifo2", stat.S_IFIFO), ("fifo3", stat.S_IFIFO), ("node", stat.S_IFREG),
                                                                                                         ("node2", stat.S_IFREG), ("node3", stat.S_IFIFO)) for st in (os.stat(name),)]
    print("mkfifo and mknod:", modes, stat.S_IMODE(os.stat("fifo").st_mode), stat.S_IMODE(os.stat("node").st_mode), sorted(os.listdir(".")))
    print("they refuse:", m(lambda: os.mkfifo("fifo")), m(lambda: os.mkfifo("missing/fifo")), m(lambda: os.mkfifo("x", 0o600, top)), m(lambda: os.mkfifo()), m(lambda: os.mkfifo(5)), m(lambda: os.mkfifo("x", "0")),  # type: ignore[arg-type, call-arg]
          m(lambda: os.mkfifo("x", dir_fd=987)), m(lambda: os.mkfifo("x", dir_fd=fd)), m(lambda: os.mkfifo("x", dir_fd="t")), m(lambda: os.mkfifo("a\0b")), m(lambda: os.mknod("node")), m(lambda: os.mknod("missing/node")),  # type: ignore[arg-type]
          m(lambda: os.mknod("x", 0o600, 0, top)), m(lambda: os.mknod()), m(lambda: os.mknod("x", "0")), m(lambda: os.mknod("x", 0o600, "0")), m(lambda: os.mknod("x", 0o600, -5)), m(lambda: os.mknod("x", stat.S_IFDIR | 0o700)),  # type: ignore[arg-type, call-arg]
          m(lambda: os.mknod("x", dir_fd=987)), m(lambda: os.mknod("x", 0o600, 2 ** 70)), sorted(os.listdir(".")) == sorted(["f", "out", "fifo", "fifo2", "fifo3", "node", "node2", "node3"]))

    # splice: from a pipe into a file, from a file into a pipe; a pipe has no offset to give
    pr, pw = os.pipe()
    os.write(pw, b"through the pipe")
    target = os.open("spliced", os.O_RDWR | os.O_CREAT, 0o600)
    moved = os.splice(pr, target, 7)
    at = os.splice(pr, target, 4, None, 20)
    print("splice:", moved, at, content("spliced"), os.lseek(target, 0, 1), os.read(pr, 100), os.splice(fd, pw, 5, 2), os.read(pr, 100), os.lseek(fd, 0, 1), os.splice(src=fd, dst=pw, count=3, offset_src=Index(0), offset_dst=None, flags=0),  # type: ignore[arg-type]
          os.read(pr, 100), os.splice(fd, pw, 0), os.splice(fd, pw, 4, 100), (os.SPLICE_F_MOVE, os.SPLICE_F_NONBLOCK, os.SPLICE_F_MORE))
    print("splice refuses:", m(lambda: os.splice(fd, pw, -1)), m(lambda: os.splice(fd, target, 4)), m(lambda: os.splice(pr, target, 4, 0)), m(lambda: os.splice(fd, pw, 4, None, 0)), m(lambda: os.splice(987, pw, 4)),
          m(lambda: os.splice(fd, 987, 4)), m(lambda: os.splice(fd, pw)), m(lambda: os.splice(fd, pw, "4")), m(lambda: os.splice(fd, pw, 4, "0")), m(lambda: os.splice(fd, pw, 4, None, "0")), m(lambda: os.splice(fd, pw, 4, None, None, -1)),  # type: ignore[call-arg, arg-type]
          m(lambda: os.splice(fd, pw, 4, None, None, 2 ** 32)), m(lambda: os.splice(fd, pw, 4, None, None, 0, 0)), m(lambda: os.splice(fd, pw, 2 ** 70)), m(lambda: os.splice(fd, pw, 4, 2 ** 70)), m(lambda: os.splice(fd, pw, 4, flag=0)),  # type: ignore[call-arg]
          m(lambda: os.splice(fd, pw, 4, None, None, "0")), m(lambda: os.splice(fd, pw, 4, -1)))  # type: ignore[arg-type]

    for descriptor in (fd, top, out, e, sem, plain, mem, pr, pw, target):
        os.close(descriptor)
    os.chdir("/")
    for name in os.listdir(d):
        os.unlink(os.path.join(d, name))
    os.rmdir(d)


if __name__ == "__main__":
    main()
