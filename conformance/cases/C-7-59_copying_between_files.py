# clause: C-7-59
# spec: section 7
# status: P1
# source: dialect specification section 7 (os, shutil), Modules/posixmodule.c (os.copy_file_range, os.sendfile, os.chmod, os.fchmod), Lib/shutil.py (copyfile and its fast paths, copymode, copy)
"""Copying between files: os.copy_file_range and os.sendfile between descriptors (what they return, which positions they move,
their offsets, the end of the input, their argument checks), os.chmod by path, by descriptor and under a directory's
descriptor, os.fchmod, and shutil's copyfile, copyfileobj, copymode and copy over them."""
# ruff: noqa: E501, PTH
import os
import shutil
import stat
import tempfile
from collections.abc import Callable


def m(f: Callable[[], object]) -> str:
    try:
        return repr(f())
    except OSError as e:
        return type(e).__name__ + ": " + repr((e.errno, e.strerror, type(e.filename).__name__))
    except Exception as e:
        return type(e).__name__ + ": " + str(e)


def mode(path: str) -> str:
    return oct(stat.S_IMODE(os.stat(path).st_mode))


def read(path: str) -> bytes:
    with open(path, "rb") as f:
        return f.read()


with tempfile.TemporaryDirectory() as d:
    a, b, c = os.path.join(d, "a"), os.path.join(d, "b"), os.path.join(d, "c")
    with open(a, "wb") as f:
        f.write(b"0123456789" * 10)
    src, dst = os.open(a, os.O_RDONLY), os.open(b, os.O_RDWR | os.O_CREAT, 0o600)

    # os.copy_file_range: both positions move unless an offset is given; the end of the input is 0
    print("copy_file_range:", os.copy_file_range(src, dst, 30), os.lseek(src, 0, os.SEEK_CUR), os.lseek(dst, 0, os.SEEK_CUR), os.copy_file_range(src, dst, 1000), os.copy_file_range(src, dst, 10), os.fstat(dst).st_size, read(b) == read(a))
    print("offsets:", os.copy_file_range(src, dst, 5, 2, 200), os.lseek(src, 0, os.SEEK_CUR), os.lseek(dst, 0, os.SEEK_CUR), os.fstat(dst).st_size, read(b)[200:], os.copy_file_range(src, dst, 4, offset_src=96), os.copy_file_range(src, dst, 3, offset_dst=0), read(b)[:4])
    print("arguments:", m(lambda: os.copy_file_range(src, dst, -1)), m(lambda: os.copy_file_range(src, dst)), m(lambda: os.copy_file_range(-1, dst, 1)), m(lambda: os.copy_file_range("a", dst, 1)), m(lambda: os.copy_file_range(src=src, dst=dst, count=0)),  # type: ignore[arg-type,call-arg]
          m(lambda: os.copy_file_range(src, dst, 1.5)), m(lambda: os.copy_file_range(src, dst, 1, "x")), m(lambda: os.copy_file_range(src, dst, 2 ** 70)), m(lambda: os.copy_file_range(src, dst, 1, 2 ** 70)), m(lambda: os.copy_file_range(src, dst, 1, None, None, 1)),  # type: ignore[arg-type,call-arg]
          m(lambda: os.copy_file_range(src, dst, 1, None, None)), m(lambda: os.copy_file_range(dst, src, 1)))

    # os.sendfile: without an offset the input's own position moves; with one it stays
    os.lseek(src, 0, os.SEEK_SET)
    out = os.open(c, os.O_WRONLY | os.O_CREAT, 0o600)
    print("sendfile:", os.sendfile(out, src, None, 15), os.lseek(src, 0, os.SEEK_CUR), os.sendfile(out, src, 50, 20), os.lseek(src, 0, os.SEEK_CUR), os.fstat(out).st_size, os.sendfile(out, src, 95, 100), os.sendfile(out, src, 1000, 5), read(c))
    print("arguments:", m(lambda: os.sendfile(out, src, 0, -1)), m(lambda: os.sendfile(out, src, 0)), m(lambda: os.sendfile(out, -1, 0, 1)), m(lambda: os.sendfile(out_fd=out, in_fd=src, offset=0, count=0)), m(lambda: os.sendfile(out, src, "x", 1)),  # type: ignore[arg-type,call-arg]
          m(lambda: os.sendfile(out, src, -1, 1)), m(lambda: os.sendfile(out, src, 0, 1, 2)), m(lambda: os.sendfile(src, out, 0, 1)), m(lambda: os.sendfile(out, src, 0, 2 ** 70)), m(lambda: os.sendfile("x", src, 0, 1)))  # type: ignore[arg-type,call-arg]

    # os.chmod and os.fchmod
    top = os.open(d, os.O_RDONLY)
    print("chmod:", m(lambda: os.chmod(a, 0o640)), mode(a), m(lambda: os.chmod(src, 0o600)), mode(a), m(lambda: os.chmod("a", 0o604, dir_fd=top)), mode(a), m(lambda: os.fchmod(src, 0o611)), mode(a), m(lambda: os.chmod(os.fsencode(a), 0o7777)), mode(a),
          m(lambda: os.chmod(a, mode=0o600)), m(lambda: os.chmod(path=a, mode=0o644)), m(lambda: os.fchmod(fd=src, mode=0o600)), mode(a), m(lambda: os.chmod(src, 0o640, dir_fd=top)), m(lambda: os.chmod(src, 0o604, follow_symlinks=False)), mode(a))
    print("arguments:", m(lambda: os.chmod(os.path.join(d, "missing"), 0o600)), m(lambda: os.chmod(a, "x")), m(lambda: os.chmod(a)), m(lambda: os.chmod(a, 2 ** 40)), m(lambda: os.chmod(-1, 0o600)), m(lambda: os.fchmod(-1, 0o600)), m(lambda: os.fchmod("a", 0o600)),  # type: ignore[arg-type,call-arg]
          m(lambda: os.chmod(a, 0o600, top)), m(lambda: os.chmod(1.5, 0o600)), m(lambda: os.chmod("missing", 0o600, dir_fd=top)), m(lambda: os.chmod(a, 0o600, dir_fd="x")), m(lambda: os.fchmod(src)), m(lambda: os.fchmod(src, 0o600, 1)),  # type: ignore[arg-type,call-arg]
          os.chmod in os.supports_fd, os.chmod in os.supports_dir_fd, hasattr(os, "lchmod"))
    for fd in (src, dst, out, top):
        os.close(fd)

    # shutil over them
    os.chmod(a, 0o640)
    copied = os.path.join(d, "copied")
    print("copyfile:", shutil.copyfile(a, copied) == copied, read(copied) == read(a), m(lambda: shutil.copyfile(a, a)), m(lambda: shutil.copyfile(os.path.join(d, "missing"), copied)), m(lambda: shutil.copyfile(a, d)), m(lambda: shutil.copyfile(d, copied)))
    big = os.path.join(d, "big")
    with open(big, "wb") as f:
        f.write(bytes(range(256)) * 20000)
    print("a larger file:", read(shutil.copyfile(big, os.path.join(d, "big2"))) == read(big), os.path.getsize(os.path.join(d, "big2")), os.path.getsize(shutil.copyfile(os.path.join(d, "c"), os.path.join(d, "empty-target"))))
    with open(os.path.join(d, "empty"), "wb"):
        pass
    print("an empty file:", os.path.getsize(shutil.copyfile(os.path.join(d, "empty"), os.path.join(d, "empty2"))))
    with open(a, "rb") as fsrc, open(os.path.join(d, "obj"), "wb") as fdst:
        shutil.copyfileobj(fsrc, fdst, 7)
    print("copyfileobj:", read(os.path.join(d, "obj")) == read(a))
    os.chmod(copied, 0o600)
    print("copymode:", shutil.copymode(a, copied), mode(copied), m(lambda: shutil.copymode(os.path.join(d, "missing"), copied)))  # type: ignore[func-returns-value]
    sub = os.path.join(d, "sub")
    os.mkdir(sub)
    os.chmod(a, 0o604)
    print("copy:", shutil.copy(a, sub) == os.path.join(sub, "a"), mode(os.path.join(sub, "a")), read(os.path.join(sub, "a")) == read(a), shutil.copy(a, os.path.join(sub, "renamed")) == os.path.join(sub, "renamed"), mode(os.path.join(sub, "renamed")),
          sorted(os.listdir(sub)), m(lambda: shutil.copy(os.path.join(d, "missing"), sub)))
print("after the with:", os.path.exists(d))
