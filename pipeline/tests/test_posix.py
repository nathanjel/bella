"""posix and os, compiled, against CPython: the messages case C-7-26 does not compare; what stops by name; and what the
named tuples and the module's functions show."""
from __future__ import annotations

import os
import pty
import shutil
import subprocess
import sys
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

# beside C-7-65 and C-7-66: the messages of the descriptor functions, of the wait statuses and of the device numbers
DESCRIPTOR_MESSAGES = r"""
import os
def m(f):
    try:
        return repr(f())
    except BaseException as e:
        return type(e).__name__ + ": " + str(e)
print(m(lambda: os.dup()), m(lambda: os.dup(fd=1)), m(lambda: os.dup("a")), m(lambda: os.dup(987)), m(lambda: os.dup2(1)), m(lambda: os.dup2(1, 2, 3, 4)), m(lambda: os.dup2(987, 986)), m(lambda: os.dup2(fd=0, fd3=1)), m(lambda: os.pipe(1)),
      m(lambda: os.pipe2()), m(lambda: os.pipe2(flags=0)), m(lambda: os.pipe2(-1)), m(lambda: os.get_inheritable()), m(lambda: os.get_inheritable(987)), m(lambda: os.set_inheritable(1)), m(lambda: os.set_inheritable(987, "x")),
      m(lambda: os.set_inheritable(987, 1)), m(lambda: os.get_blocking(987)), m(lambda: os.set_blocking(987, True)), m(lambda: os.set_blocking(1)), m(lambda: os.closerange(1)), m(lambda: os.closerange(a=1, b=2)), m(lambda: os.fchdir(987)),
      m(lambda: os.fchdir("a")), m(lambda: os.fdatasync(987)), m(lambda: os.fdatasync()), m(lambda: os.sync(1)), m(lambda: os.truncate("no such file here", 1)), m(lambda: os.truncate(987, 1)), m(lambda: os.truncate("a")),
      m(lambda: os.truncate("a", "b")), m(lambda: os.truncate(1.5, 1)), m(lambda: os.ftruncate(987, 1)), m(lambda: os.ftruncate(1)), m(lambda: os.ftruncate(fd=1, length=1)), m(lambda: os.pread(987, 1, 0)), m(lambda: os.pread(0, -1, 0)),
      m(lambda: os.pread(1, 1)), m(lambda: os.pwrite(987, b"", 0)), m(lambda: os.pwrite(1, "a", 0)), m(lambda: os.pwrite(1, b"")), m(lambda: os.lockf(987, 1, 0)), m(lambda: os.lockf(1, 1)), m(lambda: os.posix_fallocate(987, 0, 1)),
      m(lambda: os.posix_fallocate(1, 0)), m(lambda: os.posix_fadvise(987, 0, 0, 0)), m(lambda: os.posix_fadvise(1, 0, 0)), sep="\n")
print(m(lambda: os.WIFEXITED()), m(lambda: os.WIFEXITED("a")), m(lambda: os.WIFEXITED(2**40)), m(lambda: os.WIFEXITED(state=1)), m(lambda: os.WCOREDUMP(status=1)), m(lambda: os.WCOREDUMP()), m(lambda: os.waitstatus_to_exitcode(0x7f)),
      m(lambda: os.waitstatus_to_exitcode(0x137f)), m(lambda: os.waitstatus_to_exitcode(0xffff)), m(lambda: os.waitstatus_to_exitcode(-1)), m(lambda: os.waitstatus_to_exitcode("a")), m(lambda: os.waitstatus_to_exitcode()),
      m(lambda: os.major(-2)), m(lambda: os.major(2**64)), m(lambda: os.major("a")), m(lambda: os.major()), m(lambda: os.major(device=1)), m(lambda: os.minor(1.5)), m(lambda: os.makedev(2**32, 0)), m(lambda: os.makedev(0, -2)),
      m(lambda: os.makedev(2**64, 0)), m(lambda: os.makedev(1)), m(lambda: os.makedev(major=1, minor=2)), os.dup.__doc__[:20], os.WIFEXITED.__doc__[:20], os.makedev.__doc__[:20], os.pipe.__name__, os.major.__qualname__, sep="\n")
"""

# beside C-7-67: the messages of ownership and of the ids
OWNERSHIP_MESSAGES = r"""
import os
def m(f):
    try:
        return repr(f())
    except BaseException as e:
        return type(e).__name__ + ": " + str(e)
class Bad:
    def __index__(self):
        raise ValueError("from __index__")
print(m(lambda: os.chown()), m(lambda: os.chown("a", 1)), m(lambda: os.chown("a", "b", 1)), m(lambda: os.chown("a", 1, None)), m(lambda: os.chown("a", 1.5, 1)), m(lambda: os.chown("a", Bad(), 1)), m(lambda: os.chown("a", -2, 1)),
      m(lambda: os.chown("a", 1, -2)), m(lambda: os.chown("a", 2**32, 1)), m(lambda: os.chown("a", 1, 2**63)), m(lambda: os.chown("a", 2**64, 1)), m(lambda: os.chown("a", -2**70, 1)), m(lambda: os.chown(0, -1, -1, dir_fd=0)),
      m(lambda: os.chown(0, -1, -1, follow_symlinks=False)), m(lambda: os.chown(1.5, -1, -1)), m(lambda: os.chown("no such file here", -1, -1)), m(lambda: os.chown(987, -1, -1)), m(lambda: os.chown("a", -1, -1, 5)),
      m(lambda: os.fchown(987, -1, -1)), m(lambda: os.fchown("a", -1, -1)), m(lambda: os.fchown(1, "b", -1)), m(lambda: os.fchown(1)), m(lambda: os.lchown("no such file here", -1, -1)), m(lambda: os.lchown(1, -1, -1)),
      m(lambda: os.lchown("a", -1, [])), m(lambda: os.getgroups(1)), m(lambda: os.getresuid(1)), m(lambda: os.getpgrp(1)), m(lambda: os.getpgid()), m(lambda: os.getpgid("a")), m(lambda: os.getpgid(4194305)),
      m(lambda: os.getsid(pid=1)), m(lambda: os.getsid(4194305)), m(lambda: os.getpriority(1)), m(lambda: os.getpriority(99, 0)), m(lambda: os.nice()), m(lambda: os.nice("a")), m(lambda: os.getloadavg(1)), m(lambda: os.sched_yield(1)),
      m(lambda: os.getrandom()), m(lambda: os.getrandom(-1)), m(lambda: os.getrandom("a")), m(lambda: os.getrandom(1, 2, 3)), m(lambda: os.getrandom(1, 99999)), os.chown.__doc__[:20], os.getrandom.__doc__[:20], os.getpgid.__name__,
      (os.getresuid(), os.getresgid(), os.getgroups(), os.getpgrp(), os.getsid(0) > 0, os.nice(0), os.getpriority(os.PRIO_PROCESS, 0)), sep="\n")
"""

# beside C-7-68: the messages of statvfs and of the configuration functions, and the values one machine gives both sides
LIMITS_MESSAGES = r"""
import os
def m(f):
    try:
        return repr(f())
    except BaseException as e:
        return type(e).__name__ + ": " + str(e)
print(m(lambda: os.statvfs()), m(lambda: os.statvfs("no such file here")), m(lambda: os.statvfs(987)), m(lambda: os.statvfs(1.5)), m(lambda: os.fstatvfs()), m(lambda: os.fstatvfs(987)), m(lambda: os.fstatvfs("a")), m(lambda: os.fstatvfs(fd=0)),
      m(lambda: os.sysconf()), m(lambda: os.sysconf("nope")), m(lambda: os.sysconf(1.5)), m(lambda: os.sysconf(99999)), m(lambda: os.sysconf(name=1)), m(lambda: os.confstr("nope")), m(lambda: os.confstr(99999)), m(lambda: os.confstr([])),
      m(lambda: os.pathconf(".")), m(lambda: os.pathconf("no such file here", 3)), m(lambda: os.pathconf(".", 99999)), m(lambda: os.pathconf(".", "nope")), m(lambda: os.pathconf(987, 3)), m(lambda: os.pathconf(".", None)),
      m(lambda: os.fpathconf(1)), m(lambda: os.fpathconf(987, 3)), m(lambda: os.fpathconf("a", 3)), m(lambda: os.fpathconf(fd=0, name=3)), os.statvfs.__doc__[:20], os.sysconf.__doc__[:20], sep="\n")
st = os.statvfs(".")
print(st.f_bsize, st.f_frsize, st.f_blocks, st.f_files, st.f_flag, st.f_namemax, st.f_fsid, os.statvfs_result.__name__, os.statvfs_result.__module__)
print([os.sysconf(n) for n in sorted(os.sysconf_names) if n not in ("SC_AVPHYS_PAGES",)])
print([m(lambda n=n: os.confstr(n)) for n in sorted(os.confstr_names)])
print([os.pathconf(".", n) for n in sorted(os.pathconf_names)])
"""


# C-7-69: readv, preadv, writev, pwritev, readinto, eventfd, memfd_create, mkfifo, mknod and splice. The words of what they refuse,
# the DeprecationWarning of memfd_create's flags outside an int and an unsigned (unsigned_int(bitwise=True)), and what the pinned
# build says of the flags of preadv and pwritev, which it has not got (no preadv2).
VECTOR_MESSAGES = r"""
import os
import warnings
def m(f):
    try:
        with warnings.catch_warnings(record=True) as got:
            warnings.simplefilter("always")
            v = f()
        return repr(v) + "".join(" (" + type(x.message).__name__ + ": " + str(x.message) + ")" for x in got)
    except BaseException as e:
        return type(e).__name__ + ": " + str(e)
class Big:
    def __index__(self):
        return 2 ** 32
class Len:
    def __len__(self):
        raise RuntimeError("no length")
    def __getitem__(self, i):
        return bytearray(1)
r, w = os.pipe()
e = os.eventfd(0)
print(m(lambda: os.eventfd(-1)), m(lambda: os.eventfd(2 ** 32)), m(lambda: os.eventfd(2 ** 70)), m(lambda: os.eventfd("1")), m(lambda: os.eventfd(1.5)), m(lambda: os.eventfd(Big())), m(lambda: os.eventfd(0, 2 ** 40)), m(lambda: os.eventfd()),
      m(lambda: os.eventfd(0, 0, 0)), m(lambda: os.eventfd(0, flag=0)), m(lambda: os.eventfd(0, 12345)), m(lambda: os.eventfd_write(e, -1)), m(lambda: os.eventfd_write(e, 2 ** 64)), m(lambda: os.eventfd_write(e, "1")),
      m(lambda: os.eventfd_write(e, 1.5)), m(lambda: os.eventfd_write(e, 2 ** 64 - 1)), m(lambda: os.eventfd_write(e)), m(lambda: os.eventfd_write("e", 1)), m(lambda: os.eventfd_write("e", -1)), m(lambda: os.eventfd_read()),
      m(lambda: os.eventfd_read("e")), m(lambda: os.eventfd_read(1.5)), m(lambda: os.eventfd_read(e, 1)), m(lambda: os.eventfd_read(987)), m(lambda: os.eventfd_write(987, 1)), sep="\n")
print(m(lambda: os.memfd_create("n", -1)), m(lambda: os.memfd_create("n", -2 ** 31)), m(lambda: os.memfd_create("n", -2 ** 31 - 1)), m(lambda: os.memfd_create("n", 2 ** 32 - 1)), m(lambda: os.memfd_create("n", 2 ** 32) > 0),
      m(lambda: os.memfd_create("n", 2 ** 70 + 1) > 0), m(lambda: os.memfd_create("n", -2 ** 40) > 0), m(lambda: os.memfd_create("n", "x")), m(lambda: os.memfd_create("n", 1.5)), m(lambda: os.memfd_create(5)), m(lambda: os.memfd_create(None)),
      m(lambda: os.memfd_create("a\0b")), m(lambda: os.memfd_create(b"a\0b")), m(lambda: os.memfd_create()), m(lambda: os.memfd_create("n", 0, 0)), m(lambda: os.memfd_create(bytearray(b"n"))), m(lambda: os.memfd_create(nam="n")),
      m(lambda: os.memfd_create("n" * 250)), sep="\n")
print(m(lambda: os.splice(r, w, -1)), m(lambda: os.splice(r, w, 1, None, None, -1)), m(lambda: os.splice(r, w, 1, None, None, 2 ** 32)), m(lambda: os.splice(r, w, "4")), m(lambda: os.splice(r, w, 4, "0")), m(lambda: os.splice(r, w, 2 ** 70)),
      m(lambda: os.splice(r, w)), m(lambda: os.splice(r, w, 4, None, None, 0, 0)), m(lambda: os.splice(r, w, 4, flag=0)), m(lambda: os.splice(r, w, 4, None, None, "0")), m(lambda: os.splice(r, w, 4, 2 ** 70)), m(lambda: os.splice(r, w, 4, flags=1.5)),
      m(lambda: os.splice(r, w, 4, 2 ** 70, None, -1)), m(lambda: os.splice(r, w, 4, 2 ** 70, "x")), m(lambda: os.splice(r, w, -1, flags=-1)), m(lambda: os.splice("r", w, -1)), m(lambda: os.splice(r, w, 4, 0)), m(lambda: os.splice(987, w, 4)), sep="\n")
print(m(lambda: os.readv(r, 5)), m(lambda: os.readv(r, [b"xx"])), m(lambda: os.readv(r, ["xx"])), m(lambda: os.readv(r, [None])), m(lambda: os.readv(r)), m(lambda: os.readv(fd=r, buffers=[])), m(lambda: os.readv(r, [], 1)), m(lambda: os.readv("f", [])),
      m(lambda: os.readv(1.5, [])), m(lambda: os.readv(r, iter([]))), m(lambda: os.readv(r, {})), m(lambda: os.readv(r, Len())), m(lambda: os.readv("f", 5)), m(lambda: os.readv(987, [bytearray(1)])), m(lambda: os.readv(r, [bytearray(1)] * 1025)),
      m(lambda: os.preadv(r, 5, 0)), m(lambda: os.preadv(r, [], 0, 1)), m(lambda: os.preadv(r, [])), m(lambda: os.preadv(r, [], "0")), m(lambda: os.preadv(r, [], 0, "0")), m(lambda: os.preadv(r, [], 0, 2 ** 40)), m(lambda: os.preadv(r, [], 2 ** 70)),
      m(lambda: os.preadv(r, [], 0, 0, 0)), m(lambda: os.preadv(r, [], offset=0)), m(lambda: os.preadv(r, [], 1.5)), m(lambda: os.preadv(r, 5, 0, 1)), m(lambda: os.preadv(r, [5], 0, 1)), m(lambda: os.preadv(r, Len(), 0, 1)),
      m(lambda: os.preadv(r, [bytearray(1)], 0)), sep="\n")
print(m(lambda: os.writev(w, 5)), m(lambda: os.writev(w, b"ab")), m(lambda: os.writev(w, ["ab"])), m(lambda: os.writev(w)), m(lambda: os.writev(w, [], 0)), m(lambda: os.writev(fd=w, buffers=[])), m(lambda: os.writev(w, [b"a", None])),
      m(lambda: os.writev(987, [b"a"])), m(lambda: os.pwritev(w, 5, 0)), m(lambda: os.pwritev(w, [], 0, 1)), m(lambda: os.pwritev(w, [])), m(lambda: os.pwritev(w, [], "0")), m(lambda: os.pwritev(w, 5, 0, 1)), m(lambda: os.pwritev(w, [b"a"], 0)),
      m(lambda: os.pwritev(w, [], 0, 0, 0)), m(lambda: os.readinto(r, b"xx")), m(lambda: os.readinto(r, "xx")), m(lambda: os.readinto(r, 5)), m(lambda: os.readinto(r)), m(lambda: os.readinto(r, bytearray(1), 1)),
      m(lambda: os.readinto(fd=r, buffer=bytearray(1))), m(lambda: os.readinto("f", bytearray(1))), m(lambda: os.readinto("f", b"x")), m(lambda: os.readinto(987, bytearray(1))), sep="\n")
print(m(lambda: os.mkfifo("/tmp")), m(lambda: os.mkfifo()), m(lambda: os.mkfifo(5)), m(lambda: os.mkfifo("x", "0")), m(lambda: os.mkfifo("x", 0, 3)), m(lambda: os.mkfifo("x", dir_fd="t")), m(lambda: os.mkfifo("a\0b")), m(lambda: os.mkfifo("x", mod=1)),
      m(lambda: os.mkfifo(0)), m(lambda: os.mkfifo("no such directory here/x")), m(lambda: os.mknod()), m(lambda: os.mknod("x", "0")), m(lambda: os.mknod("x", 0o600, "0")), m(lambda: os.mknod("x", 0o600, -5)), m(lambda: os.mknod("x", 0o600, 2 ** 70)),
      m(lambda: os.mknod("x", 0o600, 0, 3)), m(lambda: os.mknod("x", 0o600, 1.5)), m(lambda: os.mknod("/tmp", 0o600, 2 ** 64)), m(lambda: os.mknod("/tmp")), m(lambda: os.mknod("no such directory here/x")), m(lambda: os.mknod(b"a\0b")),
      os.readv.__doc__[:30], os.eventfd.__doc__[:30], os.mkfifo.__doc__[:30], sep="\n")
"""


def test_vectors_eventfd_memfd_nodes_and_splice() -> None:
    same(VECTOR_MESSAGES)


# C-7-70: timerfd, the scheduler and sched_param, pidfd_open, ctermid, device_encoding, getlogin and getgrouplist. Their words, and
# what one machine gives both sides: its CPUs, the round-robin quantum, the login name, a user's groups.
TIMER_MESSAGES = r"""
import os
import warnings
def m(f):
    try:
        with warnings.catch_warnings(record=True) as got:
            warnings.simplefilter("always")
            v = f()
        return repr(v) + "".join(" (" + type(x.message).__name__ + ": " + str(x.message) + ")" for x in got)
    except BaseException as e:
        return type(e).__name__ + ": " + str(e)
class I:
    def __init__(self, v):
        self.v = v
    def __index__(self):
        return self.v
t = os.timerfd_create(1)
P = os.sched_param
me = os.getpid()
allowed = os.sched_getaffinity(0)
print(m(lambda: os.timerfd_create()), m(lambda: os.timerfd_create(99)), m(lambda: os.timerfd_create("x")), m(lambda: os.timerfd_create(1, 0)), m(lambda: os.timerfd_create(1, flags=12345)), m(lambda: os.timerfd_create(1, flags="x")),
      m(lambda: os.timerfd_create(clockid=1)), m(lambda: os.timerfd_create(1, flag=0)), m(lambda: os.timerfd_create(2**40)), m(lambda: os.timerfd_create(1.5)), m(lambda: os.timerfd_create(1, flags=2**40)), m(lambda: os.timerfd_create(1, clockid=1)),
      m(lambda: os.timerfd_create(flags=0)), m(lambda: os.timerfd_create(1, clockid2=1)), m(lambda: os.timerfd_create(1, flags=0, more=1)), sep="\n")
print(m(lambda: os.timerfd_settime()), m(lambda: os.timerfd_settime(987)), m(lambda: os.timerfd_settime("x")), m(lambda: os.timerfd_settime(t, 0)), m(lambda: os.timerfd_settime(t, initial="x")), m(lambda: os.timerfd_settime(t, initial=-1)),
      m(lambda: os.timerfd_settime(t, interval=-0.5)), m(lambda: os.timerfd_settime(t, initial=float("nan"))), m(lambda: os.timerfd_settime(t, initial=float("inf"))), m(lambda: os.timerfd_settime(t, initial=1e300)),
      m(lambda: os.timerfd_settime(t, initial=9.3e9)), m(lambda: os.timerfd_settime(t, flags=99)), m(lambda: os.timerfd_settime(t, flags="x")), m(lambda: os.timerfd_settime(t, initia=1)), m(lambda: os.timerfd_settime(fd=t)),
      m(lambda: os.timerfd_settime(t, initial=None)), m(lambda: os.timerfd_settime(t, interval=2**70)), m(lambda: os.timerfd_settime(t, initial=-1e-10)), m(lambda: os.timerfd_settime(t, flags="x", initial="y")),
      m(lambda: os.timerfd_settime(t, initial="y", interval=float("nan"))), m(lambda: os.timerfd_settime(t, initial=float("nan"), interval="y")), m(lambda: os.timerfd_settime(t, initial=10**400)), m(lambda: os.timerfd_settime(True)),
      m(lambda: os.timerfd_settime(t, interval=float("nan"), initial=float("inf"))), sep="\n")
print(m(lambda: os.timerfd_settime_ns()), m(lambda: os.timerfd_settime_ns(987)), m(lambda: os.timerfd_settime_ns(t, initial=1.5)), m(lambda: os.timerfd_settime_ns(t, initial=-1)), m(lambda: os.timerfd_settime_ns(t, interval=-1)),
      m(lambda: os.timerfd_settime_ns(t, initial=2**63)), m(lambda: os.timerfd_settime_ns(t, initial=-(2**63) - 1)), m(lambda: os.timerfd_settime_ns(t, interval=2**200)), m(lambda: os.timerfd_settime_ns(t, initial=I(2**63))),
      m(lambda: os.timerfd_settime_ns(t, initial="1")), m(lambda: os.timerfd_settime_ns(t, 0)), m(lambda: os.timerfd_settime_ns(t, flags=99)), m(lambda: os.timerfd_settime_ns(t, initial=None)), m(lambda: os.timerfd_settime_ns(t, flags=2**31)),
      m(lambda: os.timerfd_settime_ns(t, initial=2**63, interval="x")), m(lambda: os.timerfd_settime_ns("x", initial=2**63)), m(lambda: os.timerfd_settime_ns(t, flags="x", initial=2**63)), m(lambda: os.timerfd_settime_ns(t, initial=-(2**63))),
      m(lambda: os.timerfd_settime_ns(t, initial=1, interval=2, flags=0, extra=1)), m(lambda: os.timerfd_settime_ns(t, initial=1, initial2=2)), m(lambda: os.timerfd_settime_ns(t, **{"fd": 1})), sep="\n")
print(m(lambda: os.timerfd_gettime()), m(lambda: os.timerfd_gettime(987)), m(lambda: os.timerfd_gettime("x")), m(lambda: os.timerfd_gettime(t, 1)), m(lambda: os.timerfd_gettime(fd=t)), m(lambda: os.timerfd_gettime_ns()), m(lambda: os.timerfd_gettime_ns(987)),
      m(lambda: os.timerfd_gettime_ns(1.5)), m(lambda: os.timerfd_gettime(False) and None), m(lambda: os.timerfd_gettime_ns(t, 1)), sep="\n")
print(P, P(5), m(lambda: P()), m(lambda: P(1, 2)), m(lambda: P(sched_priority=3)), m(lambda: P(x=1)), m(lambda: P(1, sched_priority=2)), m(lambda: P(sched_priorit=2)), m(lambda: type("S", (P,), {})), m(lambda: setattr(P(1), "sched_priority", 1)),
      m(lambda: P(1).x), m(lambda: P.__new__()), m(lambda: P.__new__(int)), m(lambda: P.__new__(P)), m(lambda: P.__new__(P, 1, 2)), m(lambda: P.__new__(P, sched_priority=1)), m(lambda: P(1).__reduce__(1)), m(lambda: P.__reduce__()),
      m(lambda: P.__reduce__((1,))), m(lambda: P(1).__replace__(x=1)), m(lambda: P(1).__reduce_ex__(2)), m(lambda: P(1).__replace__(sched_priority="p")), P.__doc__, P.sched_priority, type(P.__dict__["__new__"]).__name__, sorted(P.__dict__),
      m(lambda: P([1])), m(lambda: P(1) + (2,)), m(lambda: P(1) * 2), m(lambda: P(1)[:]), m(lambda: P(3) < P(4)), sep="\n")
print(m(lambda: os.sched_get_priority_max(99)), m(lambda: os.sched_get_priority_max(-1)), m(lambda: os.sched_get_priority_max("x")), m(lambda: os.sched_get_priority_max()), m(lambda: os.sched_get_priority_max(policy=1)),
      m(lambda: os.sched_get_priority_min(policy=2)), m(lambda: os.sched_get_priority_max(2**40)), m(lambda: os.sched_get_priority_max(1.5)), m(lambda: os.sched_get_priority_max(1, 2)), m(lambda: os.sched_get_priority_max(polic=1)),
      m(lambda: os.sched_get_priority_min()), m(lambda: os.sched_get_priority_min(os.SCHED_RESET_ON_FORK)), m(lambda: os.sched_getscheduler(2**30)), m(lambda: os.sched_getscheduler(-1)), m(lambda: os.sched_getscheduler("x")),
      m(lambda: os.sched_getscheduler()), m(lambda: os.sched_getscheduler(pid=0)), m(lambda: os.sched_getscheduler(2**70)), m(lambda: os.sched_getscheduler(1.5)), m(lambda: os.sched_getparam(2**30)), m(lambda: os.sched_getparam(-1)),
      m(lambda: os.sched_getparam("x")), m(lambda: os.sched_getparam()), sep="\n")
print(m(lambda: os.sched_setparam(0, P(5))), m(lambda: os.sched_setparam(0, (0,))), m(lambda: os.sched_setparam(0, P("x"))), m(lambda: os.sched_setparam(0, P(2**40))), m(lambda: os.sched_setparam(0, P(2**70))), m(lambda: os.sched_setparam(0, P(1.5))),
      m(lambda: os.sched_setparam(2**30, P(0))), m(lambda: os.sched_setparam("x", 0)), m(lambda: os.sched_setparam(0)), m(lambda: os.sched_setparam(0, P(0), 1)), m(lambda: os.sched_setparam(pid=0, param=P(0))), m(lambda: os.sched_setparam(0, P(-1))),
      m(lambda: os.sched_setparam(0, P(-(2**40)))), m(lambda: os.sched_setparam(0, P(I(0)))), m(lambda: os.sched_setparam(0, P(None))), m(lambda: os.sched_setscheduler(0, os.SCHED_OTHER, P(3))), m(lambda: os.sched_setscheduler(0, 99, P(0))),
      m(lambda: os.sched_setscheduler(0, os.SCHED_OTHER, 0)), m(lambda: os.sched_setscheduler(0, "x", P(0))), m(lambda: os.sched_setscheduler("x", 0, 0)), m(lambda: os.sched_setscheduler(0, 0)), m(lambda: os.sched_setscheduler(2**30, 0, P(0))),
      m(lambda: os.sched_setscheduler(0, 2**40, 5)), m(lambda: os.sched_rr_get_interval(0)), m(lambda: os.sched_rr_get_interval(2**30)), m(lambda: os.sched_rr_get_interval(-1)),
      m(lambda: os.sched_rr_get_interval("x")), m(lambda: os.sched_rr_get_interval()), sep="\n")
print(sorted(allowed), m(lambda: os.sched_setaffinity(0, [])), m(lambda: os.sched_setaffinity(0, 5)), m(lambda: os.sched_setaffinity(0, ["x"])), m(lambda: os.sched_setaffinity(0, [-1])), m(lambda: os.sched_setaffinity(0, [2**31 - 1])),
      m(lambda: os.sched_setaffinity(0, [2**70])), m(lambda: os.sched_setaffinity(0, [-(2**70)])), m(lambda: os.sched_setaffinity(0, [1.5])), m(lambda: os.sched_setaffinity(0, [100000])), m(lambda: os.sched_setaffinity(2**30, allowed)),
      m(lambda: os.sched_setaffinity(0)), m(lambda: os.sched_setaffinity(0, allowed, 1)), m(lambda: os.sched_setaffinity(0, "0")), m(lambda: os.sched_setaffinity(0, [min(allowed), "x"])), m(lambda: os.sched_setaffinity("x", allowed)),
      m(lambda: os.sched_setaffinity(0, [None])), m(lambda: os.sched_setaffinity(pid=0, mask=allowed)), m(lambda: os.sched_getaffinity(2**30)), m(lambda: os.sched_getaffinity(-1)), m(lambda: os.sched_getaffinity("x")), m(lambda: os.sched_getaffinity()),
      m(lambda: os.sched_getaffinity(pid=0)), sorted(os.sched_getaffinity(0)) == sorted(allowed), os.process_cpu_count(), os.cpu_count(), sep="\n")
print(m(lambda: os.pidfd_open(2**30)), m(lambda: os.pidfd_open(-1)), m(lambda: os.pidfd_open(0)), m(lambda: os.pidfd_open()), m(lambda: os.pidfd_open("x")), m(lambda: os.pidfd_open(me, 12345)), m(lambda: os.pidfd_open(me, -1)),
      m(lambda: os.pidfd_open(me, 2**32)), m(lambda: os.pidfd_open(me, 0, 0)), m(lambda: os.pidfd_open(me, "0")), m(lambda: os.pidfd_open(me, flag=0)), m(lambda: os.pidfd_open("x", -1)), m(lambda: os.ctermid()), m(lambda: os.ctermid(1)),
      m(lambda: os.ctermid(x=1)), m(lambda: os.device_encoding(0)), m(lambda: os.device_encoding(987)), m(lambda: os.device_encoding("x")), m(lambda: os.device_encoding()), m(lambda: os.device_encoding(fd=0)), m(lambda: os.device_encoding(1.5)),
      m(lambda: os.device_encoding(-1)), m(lambda: os.device_encoding(2**40)), m(lambda: os.device_encoding(0, 1)), m(lambda: os.device_encoding(f=0)), m(lambda: os.device_encoding(True)), sep="\n")
print(m(lambda: os.getlogin()), m(lambda: os.getlogin(1)), m(lambda: os.getgrouplist("root", 0)), m(lambda: os.getgrouplist("no such user here", 5)), m(lambda: os.getgrouplist("root")), m(lambda: os.getgrouplist(b"root", 0)),
      m(lambda: os.getgrouplist("root", -1)), m(lambda: os.getgrouplist("root", 2**32)), m(lambda: os.getgrouplist("root", "0")), m(lambda: os.getgrouplist("a\0b", 0)), m(lambda: os.getgrouplist(user="root", group=0)),
      m(lambda: os.getgrouplist("root", 2**32 - 1)), m(lambda: os.getgrouplist("root", 0, 0)), m(lambda: os.getgrouplist(5, "x")), m(lambda: os.getgrouplist("\udcff", 0)), m(lambda: os.getgrouplist("root", -2)),
      m(lambda: sorted(os.getgrouplist(os.environ.get("USER", "root"), os.getgid())) == sorted(set(os.getgroups()) | {os.getgid()})), m(lambda: os.getgrouplist("root", 1.5)), sep="\n")
print(os.timerfd_create.__doc__[:60], os.timerfd_settime.__doc__[:60], os.sched_getaffinity.__doc__[:40], os.pidfd_open.__doc__[:40], os.ctermid.__doc__, os.device_encoding.__doc__[:40], os.getlogin.__doc__, os.getgrouplist.__doc__[:40], sep="\n")
"""


def test_timers_the_scheduler_and_the_process_names() -> None:
    same(TIMER_MESSAGES)


# C-7-71: the setters of ids, groups, the process group, the session and the priority. Their words, the order of two refusals in
# one call (a missing argument is said before one given twice), and what this machine's privilege lets through: setgroups and
# initgroups are refused to an ordinary user and allowed to root, the same on both sides.
SETTER_MESSAGES = r"""
import os
def m(f):
    try:
        return repr(f())
    except BaseException as e:
        return type(e).__name__ + ": " + str(e)
class I:
    def __init__(self, v):
        self.v = v
    def __index__(self):
        return self.v
class Raises:
    def __index__(self):
        raise RuntimeError("inside __index__")
class Len:
    def __len__(self):
        raise RuntimeError("no length")
    def __getitem__(self, i):
        return 0
u, g = os.getuid(), os.getgid()
gs = os.getgroups()
print(m(lambda: os.setuid(u)), m(lambda: os.setuid(I(u))), m(lambda: os.setuid(-1)), m(lambda: os.setuid(2**32)), m(lambda: os.setuid(2**32 - 1)), m(lambda: os.setuid("x")), m(lambda: os.setuid()), m(lambda: os.setuid(u, u)),
      m(lambda: os.setuid(uid=u)), m(lambda: os.setuid(1.5)), m(lambda: os.setuid(-2)), m(lambda: os.setuid(2**70)), m(lambda: os.setuid(-(2**70))), m(lambda: os.setuid(Raises())), m(lambda: os.setuid(None)), m(lambda: os.seteuid(u)),
      m(lambda: os.seteuid(-1)), m(lambda: os.seteuid("x")), m(lambda: os.seteuid()), m(lambda: os.seteuid(euid=u)), m(lambda: os.seteuid(2**32)), m(lambda: os.setgid(g)), m(lambda: os.setgid(-1)), m(lambda: os.setgid("x")),
      m(lambda: os.setgid()), m(lambda: os.setgid(gid=g)), m(lambda: os.setgid(2**32)), m(lambda: os.setgid(2**70)), m(lambda: os.setegid(g)), m(lambda: os.setegid(-1)), m(lambda: os.setegid("x")), m(lambda: os.setegid()), sep="\n")
print(m(lambda: os.setreuid(u, u)), m(lambda: os.setreuid(-1, -1)), m(lambda: os.setreuid(u)), m(lambda: os.setreuid("x", u)), m(lambda: os.setreuid(u, "x")), m(lambda: os.setreuid(ruid=u, euid=u)), m(lambda: os.setreuid(2**32, u)),
      m(lambda: os.setreuid(-2, -2)), m(lambda: os.setreuid(u, u, u)), m(lambda: os.setreuid("x", "y")), m(lambda: os.setreuid(2**70, "y")), m(lambda: os.setregid(g, g)), m(lambda: os.setregid(-1, -1)), m(lambda: os.setregid(g)),
      m(lambda: os.setregid("x", g)), m(lambda: os.setregid(g, 1.5)), m(lambda: os.setresuid(u, u, u)), m(lambda: os.setresuid(-1, -1, -1)), m(lambda: os.setresuid(u, u)), m(lambda: os.setresuid("x", u, u)), m(lambda: os.setresuid(u, u, "x")),
      m(lambda: os.setresuid(u, u, u, u)), m(lambda: os.setresuid(ruid=u, euid=u, suid=u)), m(lambda: os.setresuid(-2, u, u)), m(lambda: os.setresuid(u, 2**70, "x")), m(lambda: os.setresgid(g, g, g)), m(lambda: os.setresgid(-1, -1, -1)),
      m(lambda: os.setresgid(g, g)), m(lambda: os.setresgid(g, "x", g)), (os.getresuid(), os.getresgid()) == ((u, u, u), (g, g, g)), sep="\n")
print(m(lambda: os.setgroups(gs)), m(lambda: os.setgroups((g,))), m(lambda: os.setgroups(5)), m(lambda: os.setgroups(["x"])), m(lambda: os.setgroups([2**32])), m(lambda: os.setgroups()), m(lambda: os.setgroups(gs, 1)),
      m(lambda: os.setgroups(groups=gs)), m(lambda: os.setgroups(iter(gs))), m(lambda: os.setgroups("abc")), m(lambda: os.setgroups(range(70000))), m(lambda: os.setgroups(range(65537))), m(lambda: os.setgroups({g: 1})),
      m(lambda: os.setgroups([1.5])), m(lambda: os.setgroups([g, "x"])), m(lambda: os.setgroups(set(gs))), m(lambda: os.setgroups([-2])), m(lambda: os.setgroups(Len())), m(lambda: os.setgroups([Raises()])), m(lambda: os.setgroups([2**70, "x"])),
      m(lambda: os.setgroups(["x", 2**70])), m(lambda: os.setgroups(b"ab")), m(lambda: os.initgroups("root")), m(lambda: os.initgroups(5, 0)), m(lambda: os.initgroups("root", "x")), m(lambda: os.initgroups("a\0b", 0)),
      m(lambda: os.initgroups(username="root", gid=0)), m(lambda: os.initgroups("root", 2**32)), m(lambda: os.initgroups(5, "x")), m(lambda: os.initgroups("root", 0, 0)), m(lambda: os.initgroups(os.environ.get("USER", "root"), g)), sep="\n")
print(os.getsid(0) == os.getpid(), os.getpgrp() == os.getpid(), m(lambda: os.setsid()), m(lambda: os.setsid(1)), m(lambda: os.setsid(x=1)), m(lambda: os.setpgrp()), m(lambda: os.setpgrp(1)), m(lambda: os.setpgrp(x=1)),
      m(lambda: os.setpgid(0, os.getpgrp())), m(lambda: os.setpgid(os.getpid(), 0)), m(lambda: os.setpgid(2**30, 0)), m(lambda: os.setpgid(0, -1)), m(lambda: os.setpgid(0, 2**30)), m(lambda: os.setpgid(0)), m(lambda: os.setpgid("x", 0)),
      m(lambda: os.setpgid(0, "x")), m(lambda: os.setpgid(pid=0, pgrp=0)), m(lambda: os.setpgid(0, 0, 0)), m(lambda: os.setpgid(2**40, 0)), m(lambda: os.setpgid(-1, 0)), m(lambda: os.setpgid("x", "y")), m(lambda: os.setpgid(0, 2**40)), sep="\n")
p = os.getpriority(os.PRIO_PROCESS, 0)
print(m(lambda: os.setpriority(os.PRIO_PROCESS, 0, p)), m(lambda: os.setpriority(which=os.PRIO_PROCESS, who=os.getpid(), priority=p)), m(lambda: os.setpriority(os.PRIO_PGRP, 2**30, p)), m(lambda: os.setpriority(99, 0, p)),
      m(lambda: os.setpriority(os.PRIO_PROCESS, 0)), m(lambda: os.setpriority("x", 0, 0)), m(lambda: os.setpriority(0, "x", 0)), m(lambda: os.setpriority(0, 0, "x")), m(lambda: os.setpriority(0, 0, 0, 0)), m(lambda: os.setpriority(0, 0, priorit=0)),
      m(lambda: os.setpriority(0, 0, 2**40)), m(lambda: os.setpriority(os.PRIO_USER, 2**31 - 1, p)), m(lambda: os.setpriority(0, 2**31, p)), m(lambda: os.setpriority(0, 0, which=0)), m(lambda: os.setpriority()), m(lambda: os.setpriority(1.5, "x", "y")),
      os.getpriority(os.PRIO_PROCESS, 0) == p, os.setuid.__doc__, os.setgroups.__doc__, os.setsid.__doc__, os.setpriority.__doc__, os.initgroups.__doc__[:40], sep="\n")
"""


def test_setters_of_ids_groups_session_and_priority() -> None:
    same(SETTER_MESSAGES)


def test_device_encoding_of_a_terminal() -> None:
    """A terminal's encoding is utf-8 in UTF-8 mode, which 3.15 is in unless told otherwise (_Py_device_encoding). CPython and the
    compiled program are given the same pseudo-terminal as their standard input; their output is a pipe."""
    if shutil.which("g++") is None:
        return
    env = {k: v for k, v in os.environ.items() if k != "PYTHONUTF8"}
    with tempfile.TemporaryDirectory() as tmp:
        prog = Path(tmp, "prog.py")
        prog.write_text("import os\nprint(os.device_encoding(0), os.device_encoding(1), os.isatty(0))\n", encoding="utf-8")
        compiled = build(prog, "prog.py")
        master, slave = pty.openpty()
        try:
            ref = subprocess.run([sys.executable, str(prog)], stdin=slave, capture_output=True, text=True, check=False, env=env)
            got = subprocess.run([str(compiled)], stdin=slave, capture_output=True, text=True, check=False, env=env)
        finally:
            os.close(master)
            os.close(slave)
    assert (got.stdout, got.stderr, got.returncode) == (ref.stdout, ref.stderr, ref.returncode), (ref, got)
    assert ref.stdout == "utf-8 None True\n", ref


def test_statvfs_and_configuration_limits() -> None:
    same(LIMITS_MESSAGES)


def test_ownership_and_id_messages() -> None:
    same(OWNERSHIP_MESSAGES)


def test_descriptor_wait_status_and_device_messages() -> None:
    same(DESCRIPTOR_MESSAGES)


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
    for body, name in (("os.fork()", "os.fork"), ("os.ttyname(0)", "os.ttyname"), ("os.posix_openpt(0)", "os.posix_openpt"),
                       ("os.tcgetpgrp(0)", "os.tcgetpgrp"), ("from posix import abort; abort()", "os.abort"), ("os.write(1, memoryview(b''))", "memoryview")):
        with tempfile.TemporaryDirectory() as tmp:
            prog = Path(tmp, "prog.py")
            prog.write_text(f"import os\nprint('start')\nif __name__ == '__main__':\n    try:\n        {body}\n    except BaseException:\n        print('raised')\n", encoding="utf-8")
            got = subprocess.run([str(build(prog, "prog.py"))], capture_output=True, text=True, check=False)
        assert (got.returncode, got.stdout) == (70, "start\n") and "not implemented" in got.stderr and name in got.stderr, (body, got)


if __name__ == "__main__":
    test_scandir_and_dir_fd()
    test_copying_between_descriptors_and_chmod()
    test_extended_attributes_and_odd_times()
    test_descriptor_wait_status_and_device_messages()
    test_ownership_and_id_messages()
    test_statvfs_and_configuration_limits()
    test_messages()
    test_what_a_function_shows()
    test_a_write_goes_straight_out_and_exit_does_not_flush()
    test_what_the_runtime_has_not_stops_by_name()
