"""posix and os, compiled, against CPython: the messages case C-7-26 does not compare; what stops by name; and what the
named tuples and the module's functions show."""
from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path

from pipeline.build import build
from pipeline.tests.test_review_2026_11_03 import same

MESSAGES = r"""
import os
import posix
import sys
def show(f):
    try:
        print(repr(f()))
    except BaseException as e:
        print(type(e).__name__, e)
class P:
    def __fspath__(self):
        return 1
class Fd:
    def fileno(self):
        return "a"
s = os.terminal_size((1, 2))
for fn in (lambda: os.stat(), lambda: os.stat("a", "b"), lambda: os.stat("a", 1, 2, 3), lambda: os.stat(path="a", nothing=1), lambda: os.stat(pat="a"), lambda: os.stat("a", path="a"), lambda: os.stat(1.5), lambda: os.stat(None), lambda: os.stat(P()), lambda: os.stat("a\0b"), lambda: os.stat(b"a\0b"), lambda: os.stat(2**70), lambda: os.stat(-(2**70)), lambda: os.lstat(1), lambda: os.lstat(None), lambda: os.listdir(1.5), lambda: os.listdir("a", 1), lambda: os.listdir("a\0"),
           lambda: os.mkdir(1), lambda: os.mkdir("a", "b"), lambda: os.mkdir("a", 2**70), lambda: os.rmdir(1), lambda: os.unlink(1), lambda: os.remove(1), lambda: os.remove("a\0"), lambda: os.chdir(1.5), lambda: os.chdir(None), lambda: os.access(1, 1), lambda: os.access("a", "b"), lambda: os.access("a"), lambda: os.readlink(1), lambda: os.rename("a"), lambda: os.rename(1, "b"), lambda: os.rename("a", 1), lambda: os.replace(1, "b"), lambda: os.replace("a", 1), lambda: os.rename("a\0", "b"), lambda: os.symlink(1, "b"), lambda: os.symlink("a", 1), lambda: os.link(1, "b"), lambda: os.link("a", 1),
           lambda: os.open("a"), lambda: os.open(1, 1), lambda: os.open("a", "b"), lambda: os.open("a", 1, "c"), lambda: os.close(), lambda: os.close("a"), lambda: os.close(1.5), lambda: os.close(2**70), lambda: os.read(1), lambda: os.read(fd=1, length=1), lambda: os.read("a", 1), lambda: os.read(1, "a"), lambda: os.read(1, 2**70), lambda: os.write(1), lambda: os.write(1, "a"), lambda: os.write(1, 1), lambda: os.write(1, None), lambda: os.write("a", b""), lambda: os.lseek(1), lambda: os.lseek("a", 1, 1), lambda: os.lseek(1, "a", 1), lambda: os.lseek(1, 2**70, 1), lambda: os.lseek(1, 1, "a"), lambda: os.fstat("a"), lambda: os.fstat(), lambda: os.isatty(), lambda: os.isatty("a"), lambda: os.isatty(fd=1), lambda: os.fsync("a"), lambda: os.fsync(-1), lambda: os.fsync(Fd()), lambda: os.fsync(), lambda: os.get_terminal_size(1, 2), lambda: os.get_terminal_size("a"), lambda: os.get_terminal_size(fd=1),
           lambda: os.getcwd(1), lambda: os.getcwd(x=1), lambda: os.getcwdb(1), lambda: os.getpid(1), lambda: os.getppid(x=1), lambda: os.getuid(1), lambda: os.geteuid(1), lambda: os.getgid(1), lambda: os.getegid(1), lambda: os.cpu_count(1), lambda: os.uname(1), lambda: os.times(1), lambda: os.strerror(), lambda: os.strerror("a"), lambda: os.strerror(x=1), lambda: os.umask(), lambda: os.umask("a"), lambda: os.urandom(), lambda: os.urandom("a"), lambda: os.urandom(-1), lambda: os.urandom(2**70),
           lambda: os.putenv("a"), lambda: os.putenv(1, "a"), lambda: os.putenv("a", 1), lambda: os.putenv("a=b", "c"), lambda: os.putenv("a\0", "c"), lambda: os.putenv("a", "c\0"), lambda: os.unsetenv(), lambda: os.unsetenv(1), lambda: os.unsetenv("a\0"), lambda: os.fspath(), lambda: os.fspath(1), lambda: os.fspath(P()), lambda: os.fspath(None), lambda: os._exit(), lambda: os._exit("a"), lambda: os.register_at_fork(), lambda: os.register_at_fork(1), lambda: os.register_at_fork(before=1), lambda: os.register_at_fork(after_in_child=None), lambda: os.register_at_fork(after_in_parent="a"), lambda: os.register_at_fork(nothing=1), lambda: posix._path_normpath(), lambda: posix._path_normpath(1), lambda: posix._path_normpath(P()), lambda: posix._path_splitroot_ex(1), lambda: posix._path_splitroot_ex(),
           lambda: os.DirEntry(), lambda: os.stat_result(), lambda: os.stat_result(1), lambda: os.stat_result(range(9)), lambda: os.stat_result(range(20)), lambda: os.stat_result(range(10), 1), lambda: os.stat_result(range(10), None), lambda: os.stat_result(range(10), {"x": 1}), lambda: os.stat_result(range(10), {}, 1), lambda: os.stat_result(sequence=range(10), nothing=1), lambda: os.stat_result(sequence=range(10), dic={}), lambda: os.stat_result(range(10), sequence=1), lambda: os.stat_result(range(10), {}, dict={}), lambda: os.stat_result(dict={}), lambda: os.stat_result.__new__(), lambda: os.stat_result.__new__(1), lambda: os.stat_result.__new__(int, range(10)), lambda: os.terminal_size(range(1)), lambda: os.terminal_size(range(3)), lambda: os.terminal_size(range(2), {"x": 1}),
           lambda: type("X", (os.stat_result,), {}), lambda: setattr(s, "columns", 1), lambda: delattr(s, "columns"), lambda: setattr(s, "other", 1), lambda: s.other, lambda: vars(s), lambda: os.terminal_size.columns, lambda: type(os.terminal_size.columns).__name__, lambda: os.terminal_size.columns.__get__(1), lambda: os.terminal_size.__repr__(), lambda: os.terminal_size.__repr__(1), lambda: os.terminal_size.__repr__(s, 1), lambda: os.terminal_size.__repr__(s, x=1), lambda: os.terminal_size.__reduce__(), lambda: os.terminal_size.__reduce__(1), lambda: os.terminal_size.__reduce__(s, 1), lambda: s.__reduce__(x=1), lambda: s.__replace__(1), lambda: s.__replace__(x=1), lambda: s.__replace__(x=1, y=2), lambda: os.terminal_size.__replace__(), lambda: os.terminal_size.__replace__(1), lambda: os.stat_result(range(10)).__replace__(), lambda: s.__reduce__(), lambda: s.__replace__(lines=5),
           lambda: os.environ[1], lambda: os.environ["NOTHING_SET_HERE"], lambda: os.environb["a"], lambda: os.environ.__setitem__(1, "a"), lambda: os.environ.__setitem__("a", 1), lambda: os.getenv(1), lambda: os.getenvb("a"), lambda: os.makedirs("/"), lambda: os.path.join(1), lambda: os.path.join("a", b"b"), lambda: os.path.commonpath([]), lambda: os.path.commonpath(["/a", "b"]),
           lambda: os.fsencode(1), lambda: os.fsdecode(1), lambda: os.fsencode("\ud800"), lambda: sys.audit(), lambda: sys.audit(1), lambda: sys.audit("e", 1, 2), lambda: sys.audit(event="e"), lambda: sys.getfilesystemencoding(1), lambda: sys.getfilesystemencodeerrors(1)):
    show(fn)
"""

SHOWN = r"""
import os
import posix
import sys
print(os.getcwd.__name__, os.getcwd.__qualname__, os.getcwd.__module__, os.getcwd.__self__ is posix, type(os.getcwd).__name__, os.getcwd.__doc__)
print(os.abort.__name__, os.abort.__qualname__, os.abort.__module__, os.abort.__self__ is posix, type(os.abort).__name__, os.abort.__doc__)
print(repr(os.stat)[:25], repr(os.fork)[:25], print.__doc__ is not None, len.__doc__, sys.exit.__doc__, print.__self__, posix.stat.__self__)
print(hasattr(os, "fork"), hasattr(os, "scandir"), hasattr(os, "nothing"), hasattr(posix, "nothing"))
print(os.stat in os.supports_dir_fd, os.stat in os.supports_fd, os.stat in os.supports_follow_symlinks, os.access in os.supports_effective_ids, sorted(f.__name__ for f in os.supports_dir_fd), sorted(f.__name__ for f in os.supports_fd), sorted(f.__name__ for f in os.supports_follow_symlinks))
print(os.write(1, b""), sys.modules["posix"] is posix)
"""

ORDER = r"""
import os
import sys
print("first")
sys.stdout.flush()
os.write(1, b"second\n")
print("third")
sys.stdout.flush()
os.write(2, b"to stderr\n")
os._exit(3)
"""

# os.scandir and dir_fd beside C-7-58: what the case leaves out, and what walks a tree with them
SCANDIR = r"""
import glob, os, shutil, stat, sys, tempfile, warnings
def m(f):
    try:
        return repr(f())
    except OSError as e:
        return type(e).__name__ + ": " + repr((e.errno, e.strerror, type(e.filename).__name__))
    except Exception as e:
        return type(e).__name__ + ": " + str(e)
class Bytes:
    def __init__(self, path): self.path = path
    def __fspath__(self): return os.fsencode(self.path)
root = tempfile.mkdtemp()
try:
    for i in range(300):
        open(os.path.join(root, "f%03d" % i), "w").close()
    os.makedirs(os.path.join(root, "a", "b", "c"))
    open(os.path.join(root, "a", "b", "leaf.txt"), "w").close()
    os.symlink("a", os.path.join(root, "to-a"))
    names = sorted(e.name for e in os.scandir(root))
    print(len(names), names[:2], names[-3:], sorted(type(e.name).__name__ for e in os.scandir(Bytes(root)))[:1], sorted(type(e.path).__name__ for e in os.scandir(Bytes(root)))[:1])
    print([(d.removeprefix(root), sorted(ds), sorted(fs)[:2]) for d, ds, fs in sorted(os.walk(root))])
    print(sorted((d.removeprefix(root), sorted(ds), sorted(fs)[:1]) for d, ds, fs in os.walk(root, followlinks=True))[:5], sorted(d.removeprefix(root) for d, ds, fs in os.walk(root, topdown=False))[:4])
    print(sorted(glob.glob("f00[0-3]", root_dir=root)), sorted(glob.glob("**/*.txt", root_dir=root, recursive=True)), sorted(glob.glob(os.path.join(glob.escape(root), "a", "*")))[0].removeprefix(root))
    file_fd = os.open(os.path.join(root, "f000"), os.O_RDONLY)
    top = os.open(root, os.O_RDONLY)
    print(m(lambda: os.scandir(file_fd)), m(lambda: os.stat(top, dir_fd=top)), m(lambda: os.stat(top, follow_symlinks=False)), m(lambda: os.stat("f000", dir_fd="a")), m(lambda: os.stat("f000", dir_fd=1.5)),
          m(lambda: os.lstat("f000", dir_fd=2 ** 40)), m(lambda: os.unlink("f000", dir_fd="a")), m(lambda: os.open("f000", os.O_RDONLY, dir_fd=None) > 0), m(lambda: os.stat("f000", dir_fd=None).st_size))
    made = os.open("made.txt", os.O_WRONLY | os.O_CREAT, 0o600, dir_fd=top)
    os.write(made, b"made")
    os.close(made)
    print(os.stat("made.txt", dir_fd=top).st_size, stat.S_IMODE(os.lstat("made.txt", dir_fd=top).st_mode) == 0o600, m(lambda: os.remove("made.txt", dir_fd=top)), m(lambda: os.remove("made.txt", dir_fd=top)))
    entry = next(e for e in os.scandir(root) if e.name == "to-a")
    print(m(lambda: os.DirEntry.stat()), m(lambda: os.DirEntry.stat(1)), m(lambda: os.DirEntry.is_dir(entry)), m(lambda: os.DirEntry.inode(entry, 1)), m(lambda: os.DirEntry.__fspath__(entry).removeprefix(root)),
          m(lambda: entry.is_dir(follow_symlinks=0)), m(lambda: entry.is_file(follow_symlinks=[])), m(lambda: entry.is_junction(1)), m(lambda: entry.__fspath__(1)), m(lambda: entry.stat(follow_symlinks=False).st_size > 0),
          type(os.DirEntry.__dict__["name"]).__name__, type(os.DirEntry.__dict__["stat"]).__name__, m(lambda: os.DirEntry.name.__get__(entry)), os.DirEntry.__qualname__)
    it = os.scandir(top)
    print(type(it).__qualname__, m(lambda: type(it).close()), m(lambda: it.close(1)), m(lambda: it.__enter__(1)), m(lambda: it.__exit__()), m(lambda: it.__exit__(1, 2, 3, 4)), m(lambda: next(it)), m(lambda: type(it).__next__(1)))
    seen = []
    sys.unraisablehook = lambda u: seen.append((u.exc_type.__name__, str(u.exc_value).split(" <")[0], u.err_msg.split(" <")[0]))
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        dropped = os.scandir(root)
        del dropped
    print(seen)
    os.close(file_fd)
    os.close(top)
finally:
    shutil.rmtree(root)
print(os.path.exists(root))
"""

# beside C-7-59: what depends on the kernel and the C library (a link's own mode), and odd modes
COPYING = r"""
import os, shutil, stat, tempfile
def m(f):
    try:
        return repr(f())
    except OSError as e:
        return type(e).__name__ + ": " + repr((e.errno, e.strerror))
    except Exception as e:
        return type(e).__name__ + ": " + str(e)
with tempfile.TemporaryDirectory() as d:
    a = os.path.join(d, "a")
    open(a, "w").close()
    os.symlink("a", os.path.join(d, "l"))
    top = os.open(d, os.O_RDONLY)
    src = os.open(a, os.O_RDONLY)
    mode = lambda: oct(stat.S_IMODE(os.stat(a).st_mode))
    print(m(lambda: os.chmod(a, 0o600, follow_symlinks=False)), mode(), m(lambda: os.chmod(os.path.join(d, "l"), 0o640, follow_symlinks=False)), mode(), m(lambda: os.chmod("l", 0o600, dir_fd=top, follow_symlinks=False)),
          m(lambda: os.chmod("a", 0o640, dir_fd=top, follow_symlinks=False)), mode(), m(lambda: os.chmod(os.path.join(d, "l"), 0o604)), mode(), m(lambda: os.chmod(a, -1)), mode(), m(lambda: os.chmod(a, 0o640, follow_symlinks=1)), mode(),
          m(lambda: os.copy_file_range(src, src, 1, offset_src=-1)), m(lambda: os.sendfile(src, src, 0, 1)), m(lambda: os.chmod(a, 0o600, dir_fd=None)), m(lambda: os.fchmod(top, 0o700)), oct(stat.S_IMODE(os.stat(d).st_mode)))
    with open(a, "wb") as f:
        f.write(b"x" * 300000)
    with open(a, "rb") as fsrc, open(os.path.join(d, "b"), "wb") as fdst:
        print(m(lambda: os.copy_file_range(fsrc.fileno(), fdst.fileno(), 100000)), m(lambda: os.sendfile(fdst.fileno(), fsrc.fileno(), None, 100000)), fsrc.tell(), m(lambda: shutil.copyfileobj(fsrc, fdst)))
    print(os.path.getsize(os.path.join(d, "b")), shutil.copy(a, os.path.join(d, "c")) == os.path.join(d, "c"), open(os.path.join(d, "c"), "rb").read() == b"x" * 300000)
"""

# beside C-7-60: the extended attributes (which a file system may not have: both sides run on one here, under the working
# directory), copy2 carrying them over, and times given as other real numbers or at the edge of time_t
XATTRS = r'''
import os, shutil, tempfile, decimal, fractions
def m(f):
    try:
        return repr(f())
    except OSError as e:
        return type(e).__name__ + ": " + repr((e.errno, e.strerror, type(e.filename).__name__))
    except Exception as e:
        return type(e).__name__ + ": " + str(e)
d = tempfile.mkdtemp(dir=os.getcwd())
try:
    a = os.path.join(d, "a")
    open(a, "w").close()
    os.symlink("a", os.path.join(d, "l"))
    fd = os.open(a, os.O_RDONLY)
    print(m(lambda: os.listxattr(a)), m(lambda: os.setxattr(a, "user.one", b"1")), m(lambda: os.setxattr(a, b"user.two", bytearray(b"22"), os.XATTR_CREATE)), m(lambda: sorted(os.listxattr(a))), m(lambda: os.getxattr(a, "user.one")), m(lambda: os.getxattr(fd, b"user.two")),
          m(lambda: os.setxattr(a, "user.one", b"x", os.XATTR_CREATE)), m(lambda: os.setxattr(a, "user.none", b"x", os.XATTR_REPLACE)), m(lambda: os.setxattr(fd, "user.big", b"v" * 5000)), m(lambda: len(os.getxattr(a, "user.big"))), m(lambda: os.removexattr(a, "user.big")),
          m(lambda: os.removexattr(a, "user.big")), m(lambda: os.getxattr(a, "user.missing")), m(lambda: sorted(os.listxattr(fd))), m(lambda: sorted(os.listxattr(os.fsencode(a)))), m(lambda: os.listxattr(os.path.join(d, "l"), follow_symlinks=False)), m(lambda: sorted(os.listxattr(os.path.join(d, "l")))))
    print(m(lambda: os.listxattr(fd, follow_symlinks=False)), m(lambda: os.getxattr(fd, "user.one", follow_symlinks=False)), m(lambda: os.setxattr(fd, "user.one", b"", follow_symlinks=False)), m(lambda: os.removexattr(fd, "user.one", follow_symlinks=False)),
          m(lambda: os.getxattr(a, 1)), m(lambda: os.setxattr(a, "user.one", "str")), m(lambda: os.setxattr(a, "user.one", b"1", "x")), m(lambda: os.getxattr(a)), m(lambda: os.setxattr(a, "user.one")), m(lambda: os.removexattr(a)), m(lambda: os.listxattr(a, False)),
          m(lambda: os.getxattr(os.path.join(d, "missing"), "user.one")), m(lambda: os.listxattr(-1)), m(lambda: os.getxattr(a, "user.one", False)), m(lambda: os.setxattr(a, "bad\0name", b"1")), m(lambda: os.listxattr(1.5)), m(lambda: os.getxattr(path=a, attribute="user.one")))
    b = shutil.copy2(a, os.path.join(d, "b"))
    print(m(lambda: sorted(os.listxattr(b))), m(lambda: os.getxattr(b, "user.two")))
    here = os.getcwd(); os.chdir(d); print(m(lambda: os.listxattr()), m(lambda: os.listxattr(None))); os.chdir(here)
    print(m(lambda: os.utime(a, (decimal.Decimal("1.5"), fractions.Fraction(5, 2)))), os.stat(a).st_atime_ns, os.stat(a).st_mtime_ns, m(lambda: os.utime(a, (2 ** 63, 0))), m(lambda: os.utime(a, (9223372036854775808.0, 0))), m(lambda: os.utime(a, (-9223372036854775808.0, 0))), m(lambda: os.utime(a, (1e-10, -1e-10))), os.stat(a).st_atime_ns, os.stat(a).st_mtime_ns)
    os.close(fd)
finally:
    shutil.rmtree(d)
'''


def test_extended_attributes_and_odd_times() -> None:
    same(XATTRS)


def test_copying_between_descriptors_and_chmod() -> None:
    same(COPYING)


def test_scandir_and_dir_fd() -> None:
    same(SCANDIR)


def test_messages() -> None:
    same(MESSAGES)


def test_what_a_function_shows() -> None:
    same(SHOWN)


def test_a_write_goes_straight_out_and_exit_does_not_flush() -> None:
    same(ORDER)


def test_what_the_runtime_has_not_stops_by_name() -> None:
    for body, name in (("os.fork()", "os.fork"), ("os.chown('x', 0, 0)", "os.chown"), ("os.getloadavg()", "os.getloadavg"),
                       ("os.sched_param(1)", "os.sched_param"), ("from posix import abort; abort()", "os.abort"), ("os.write(1, memoryview(b''))", "memoryview")):
        with tempfile.TemporaryDirectory() as tmp:
            prog = Path(tmp, "prog.py")
            prog.write_text(f"import os\nprint('start')\nif __name__ == '__main__':\n    try:\n        {body}\n    except BaseException:\n        print('raised')\n", encoding="utf-8")
            got = subprocess.run([str(build(prog, "prog.py"))], capture_output=True, text=True, check=False)
        assert (got.returncode, got.stdout) == (70, "start\n") and "not implemented" in got.stderr and name in got.stderr, (body, got)


if __name__ == "__main__":
    test_scandir_and_dir_fd()
    test_copying_between_descriptors_and_chmod()
    test_extended_attributes_and_odd_times()
    test_messages()
    test_what_a_function_shows()
    test_a_write_goes_straight_out_and_exit_does_not_flush()
    test_what_the_runtime_has_not_stops_by_name()
