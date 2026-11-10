# clause: C-7-60
# spec: section 7
# status: P1
# source: dialect specification section 7 (os, shutil), Modules/posixmodule.c (os.utime), Python/pytime.c (_PyTime_ObjectToTimespec), Lib/shutil.py (copystat, copy2, copytree, move)
"""os.utime: the two times given as seconds (ints, or floats rounded down to the nanosecond), as nanoseconds, or left to be now;
by path, by descriptor, under a directory's descriptor and for a link itself; its argument checks. And what shutil builds on
it: copystat, copy2, copytree (with links kept or followed, names ignored, into an existing tree) and move."""
# ruff: noqa: E501, PTH
# The times set here stay between 1901 and 2038 and no value is read back after a file was opened; what a file system can hold
# beyond that, and whether reading moves the time of access, differ from one to the next.
import os
import shutil
import stat
import tempfile
import time
from collections.abc import Callable


def m(f: Callable[[], object]) -> str:
    try:
        return repr(f())
    except OSError as e:
        return type(e).__name__ + ": " + repr((e.errno, e.strerror, type(e.filename).__name__))
    except Exception as e:
        return type(e).__name__ + ": " + str(e)


def times(path: str, follow: bool = True) -> tuple[int, int]:
    st = os.stat(path, follow_symlinks=follow)
    return st.st_atime_ns, st.st_mtime_ns


def modified(path: str) -> int:
    """The time of the last change alone: reading a file to copy it moves its time of access."""
    return os.stat(path).st_mtime_ns


def tree(root: str) -> list[tuple[str, str]]:
    out = []
    for where, dirs, files in os.walk(root):
        for name in sorted(dirs) + sorted(files):
            path = os.path.join(where, name)
            kind = "link" if os.path.islink(path) else "dir" if os.path.isdir(path) else "file"
            out.append((os.path.relpath(path, root), kind))
    return sorted(out)


class Divides:
    def __init__(self, result: object) -> None:
        self.result = result

    def __divmod__(self, other: object) -> object:
        return self.result


with tempfile.TemporaryDirectory() as d:
    a = os.path.join(d, "a")
    with open(a, "w") as f:
        f.write("content")
    link = os.path.join(d, "link")
    os.symlink("a", link)
    fd, top = os.open(a, os.O_RDONLY), os.open(d, os.O_RDONLY)

    # the times, in each form
    print("seconds:", m(lambda: os.utime(a, (1000000000, 1500000000))), times(a), m(lambda: os.utime(a, (1.5, 2.25))), times(a), m(lambda: os.utime(a, (-1.5, 0.9999999999))), times(a), m(lambda: os.utime(a, (True, 2000000000))), times(a))
    print("nanoseconds:", m(lambda: os.utime(a, ns=(1, 2000000003))), times(a), m(lambda: os.utime(a, ns=(-1, 10 ** 18))), times(a), m(lambda: os.utime(a, None, ns=(5, 6))), times(a), m(lambda: os.utime(a, ns=(Divides((7, 8)), Divides((9, 10))))), times(a))  # type: ignore[arg-type]
    before = time.time()
    print("now:", m(lambda: os.utime(a)), abs(os.stat(a).st_mtime - before) < 60, m(lambda: os.utime(a, None)), abs(os.stat(a).st_atime - before) < 60, m(lambda: os.utime(a, times=None)))
    print("ways:", m(lambda: os.utime(fd, (10, 20))), times(a), m(lambda: os.utime("a", (30, 40), dir_fd=top)), times(a), m(lambda: os.utime(link, (50, 60))), times(a), m(lambda: os.utime(link, (70, 80), follow_symlinks=False)), times(a), times(link, False),
          m(lambda: os.utime("link", (90, 100), dir_fd=top, follow_symlinks=False)), times(link, False), m(lambda: os.utime(os.fsencode(a), ns=(11, 12))), times(a), m(lambda: os.utime(path=a, times=(13, 14))), times(a))
    print("arguments:", m(lambda: os.utime(a, (1, 2), ns=(1, 2))), m(lambda: os.utime(a, (1, 2), ns=None)), m(lambda: os.utime(a, ns=None)), m(lambda: os.utime(a, [1, 2])), m(lambda: os.utime(a, (1,))), m(lambda: os.utime(a, (1, 2, 3))), m(lambda: os.utime(a, ns=[1, 2])),  # type: ignore[arg-type]
          m(lambda: os.utime(a, ("1", 2))), m(lambda: os.utime(a, (float("nan"), 2))), m(lambda: os.utime(a, (float("inf"), 2))), m(lambda: os.utime(a, (2 ** 70, 2))), m(lambda: os.utime(a, (1e30, 2))), m(lambda: os.utime(a, ns=(1.5, 2))),  # type: ignore[arg-type]
          m(lambda: os.utime(a, ns=("1", 2))), m(lambda: os.utime(a, ns=(2 ** 100, 2))), m(lambda: os.utime(a, ns=(Divides(3), 2))), m(lambda: os.utime(a, ns=(Divides((1, 2, 3)), 2))), m(lambda: os.utime(a, ns=(Divides(("a", 1)), 2))), m(lambda: os.utime(a, ns=(Divides((1, 2 ** 70)), 2))))  # type: ignore[arg-type]
    print("more:", m(lambda: os.utime(fd, (1, 2), dir_fd=top)), m(lambda: os.utime(fd, (1, 2), follow_symlinks=False)), m(lambda: os.utime(os.path.join(d, "missing"), (1, 2))), m(lambda: os.utime(-1, (1, 2))), m(lambda: os.utime()), m(lambda: os.utime(a, (1, 2), (3, 4))),  # type: ignore[call-arg]
          m(lambda: os.utime(1.5, (1, 2))), m(lambda: os.utime(a, (1, 2), dir_fd="x")), m(lambda: os.utime("missing", (1, 2), dir_fd=top)), os.utime in os.supports_fd, os.utime in os.supports_dir_fd, os.utime in os.supports_follow_symlinks)  # type: ignore[arg-type]
    os.close(fd)
    os.close(top)

    # shutil over it
    os.utime(a, (1000000000, 1500000000))
    os.chmod(a, 0o640)
    b = os.path.join(d, "b")
    with open(b, "w") as f:
        f.write("other")
    print("copystat:", shutil.copystat(a, b), modified(b), oct(stat.S_IMODE(os.stat(b).st_mode)), open(b).read(), m(lambda: shutil.copystat(os.path.join(d, "missing"), b)))  # type: ignore[func-returns-value]
    c = shutil.copy2(a, os.path.join(d, "c"))
    print("copy2:", os.path.basename(c), modified(c), oct(stat.S_IMODE(os.stat(c).st_mode)), open(c).read(), m(lambda: shutil.copy2(os.path.join(d, "missing"), c)))
    src = os.path.join(d, "src")
    os.makedirs(os.path.join(src, "pkg", "deep"))
    for name, text in (("top.txt", "t"), (os.path.join("pkg", "mod.py"), "m"), (os.path.join("pkg", "skip.pyc"), "s"), (os.path.join("pkg", "deep", "leaf.txt"), "l")):
        with open(os.path.join(src, name), "w") as f:
            f.write(text)
    os.symlink("top.txt", os.path.join(src, "to-top"))
    os.symlink("pkg", os.path.join(src, "to-pkg"))
    os.utime(os.path.join(src, "pkg"), (2000000000, 2100000000))
    os.utime(os.path.join(src, "top.txt"), (1700000000, 1800000000))
    one = shutil.copytree(src, os.path.join(d, "one"))
    print("copytree:", os.path.basename(one), tree(one), modified(os.path.join(one, "pkg")), modified(os.path.join(one, "top.txt")), open(os.path.join(one, "to-top")).read())
    two = shutil.copytree(src, os.path.join(d, "two"), symlinks=True, ignore=shutil.ignore_patterns("*.pyc", "deep"))
    print("links kept, names ignored:", tree(two), os.readlink(os.path.join(two, "to-top")), m(lambda: shutil.copytree(src, two)), m(lambda: shutil.copytree(os.path.join(d, "missing"), os.path.join(d, "never"))))
    three = os.path.join(d, "three")
    os.makedirs(os.path.join(three, "pkg"))
    with open(os.path.join(three, "pkg", "kept.txt"), "w") as f:
        f.write("k")
    print("into a tree that is there:", tree(shutil.copytree(src, three, dirs_exist_ok=True, symlinks=True)))
    moved = shutil.move(os.path.join(d, "one"), os.path.join(d, "moved"))
    print("move:", os.path.basename(moved), os.path.exists(os.path.join(d, "one")), tree(moved) == tree(one) or len(tree(moved)), os.path.basename(shutil.move(c, moved)), sorted(os.listdir(moved))[:2], m(lambda: shutil.move(os.path.join(d, "missing"), moved)),
          os.path.basename(shutil.move(os.path.join(moved, "top.txt"), os.path.join(d, "renamed.txt"))), open(os.path.join(d, "renamed.txt")).read())
    shutil.rmtree(src)
    print("rmtree:", os.path.exists(src), sorted(os.listdir(d)))
print("after the with:", os.path.exists(d))
