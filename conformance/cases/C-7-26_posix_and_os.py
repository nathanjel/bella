# clause: C-7-26
# spec: section 7
# status: P1
# source: dialect specification section 7, Modules/posixmodule.c, Objects/structseq.c, Lib/os.py, Lib/posixpath.py, Lib/genericpath.py
"""os over posix: the module's names as CPython has them, whether the runtime does the call yet or not; its named tuples;
the system calls on a directory of the case's own, with what each error carries; paths as str, bytes, PathLike and file
descriptors; and what os and posixpath build from them."""
# ruff: noqa: ANN001, ANN002, ANN003, ANN201, ANN202, ANN204, B018, B023, E731, PLR0133, PLW1508, PTH100, PTH101, PTH102, PTH103, PTH104, PTH105, PTH106, PTH107, PTH108, PTH109, PTH110, PTH111, PTH112, PTH113, PTH114, PTH115, PTH116, PTH117, PTH118, PTH119, PTH120, PTH122, PTH123, PTH202, PTH204, PTH205, S108, S605, SIM115, UP024
import os
import posix
import posixpath
import stat
import sys


def failed(f):  # type: ignore[no-untyped-def]
    try:
        f()
    except Exception as exc:
        return type(exc).__name__
    return "no error"


base = "/tmp/bella-c726-" + str(os.getpid())


def shown(value):  # type: ignore[no-untyped-def]
    """What the case prints of a path: nothing of where it is."""
    if isinstance(value, str):
        return value.replace(base, "<base>")
    if isinstance(value, bytes):
        return value.replace(os.fsencode(base), b"<base>")
    if value is None or isinstance(value, int):
        return value
    return type(value).__name__


def attempt(f, *args, **kwds):  # type: ignore[no-untyped-def]
    """The result, or what an OSError carries."""
    try:
        return f(*args, **kwds)
    except OSError as exc:
        return [type(exc).__name__, exc.errno, exc.strerror, shown(exc.filename), shown(exc.filename2), [shown(a) for a in exc.args]]  # type: ignore[no-untyped-call]


# ---- the module as CPython has it
print(sys.getfilesystemencoding(), sys.getfilesystemencodeerrors())
print(sys.builtin_module_names)
print("posix" in sys.builtin_module_names, "nt" in sys.builtin_module_names)
print(type(posix).__name__, posix.__name__)
for name in sorted(vars(posix)):
    if name.startswith("__") or name == "environ":
        continue
    value = getattr(posix, name)
    if isinstance(value, type):
        print(name, "type", value.__name__, value.__qualname__, value.__module__)
    elif callable(value):
        print(name, type(value).__name__, value.__name__, value.__qualname__, value.__module__, repr(value.__doc__))
    else:
        print(name, type(value).__name__, value)
print(type(posix.environ).__name__)
print(posix.error is OSError, os.error is OSError)
print(sorted(os.__all__))
print(sorted(n for n in dir(os) if not n.startswith("__")))
print(os.name, repr(os.sep), repr(os.linesep), repr(os.curdir), repr(os.pardir), repr(os.extsep), repr(os.altsep), repr(os.pathsep), repr(os.defpath), repr(os.devnull))
print(os.path is posixpath, sys.modules["os.path"] is posixpath, os.path.__name__)

# ---- the named tuples
for cls in (os.stat_result, os.terminal_size, os.times_result, os.uname_result, os.statvfs_result, os.waitid_result):
    print(repr(cls), cls.__name__, cls.__qualname__, cls.__module__, [c.__name__ for c in cls.__mro__], repr(cls.__doc__))
    print(cls.n_fields, cls.n_sequence_fields, cls.n_unnamed_fields, cls.__match_args__)
    print(list(vars(cls)))
    print(failed(lambda: type("X", (cls,), {})), failed(lambda: cls()), failed(lambda: cls(1)), failed(lambda: cls(range(1), {}, 1)), failed(lambda: cls(range(cls.n_sequence_fields), 1)))  # type: ignore[arg-type,call-arg,no-untyped-call]
    print(failed(lambda: cls(range(cls.n_sequence_fields - 1))), failed(lambda: cls(range(cls.n_fields + 1))), failed(lambda: cls(range(cls.n_sequence_fields), {"nothing": 1})))  # type: ignore[arg-type,no-untyped-call]
    print(failed(lambda: cls.__new__()), failed(lambda: cls.__new__(1)), failed(lambda: cls.__new__(int, range(cls.n_sequence_fields))), failed(lambda: cls(sequence=range(cls.n_sequence_fields), nothing=1)))  # type: ignore[arg-type,call-arg,no-untyped-call,type-var]
    made = cls(range(cls.n_sequence_fields))  # type: ignore[arg-type]
    print(repr(made), str(made), len(made), tuple(made), made[0], made[-1], made[1:3], list(made)[:2], type(made).__name__)
    print(made == tuple(made), tuple(made) == made, hash(made) == hash(tuple(made)), made + (1,), made * 0, 0 in made, type(made[:1]).__name__, bool(made))
    print(made.__reduce__()[0] is cls, made.__reduce__()[1], len(made.__reduce__()))
    keyed = cls(sequence=range(cls.n_sequence_fields), dict={})  # type: ignore[arg-type]
    print(keyed == made, failed(lambda: cls(range(cls.n_sequence_fields), None)), failed(lambda: cls(range(cls.n_sequence_fields), dict=None)))  # type: ignore[arg-type,no-untyped-call]
    print(failed(lambda: setattr(made, cls.__match_args__[0], 1)), failed(lambda: delattr(made, cls.__match_args__[0])), failed(lambda: setattr(made, "other", 1)), failed(lambda: made.other), failed(lambda: vars(made)))  # type: ignore[no-untyped-call,union-attr]
    print(getattr(made, cls.__match_args__[0]), vars(cls)[cls.__match_args__[0]].__get__(made), vars(cls)[cls.__match_args__[0]].__name__, failed(lambda: vars(cls)[cls.__match_args__[0]].__get__(1)))  # type: ignore[no-untyped-call]
    print(failed(lambda: cls.__repr__()), failed(lambda: cls.__repr__(1)), failed(lambda: cls.__repr__(made, 1)), failed(lambda: cls.__reduce__()), failed(lambda: cls.__reduce__(1)), failed(lambda: cls.__reduce__(made, 1)))  # type: ignore[call-arg,no-untyped-call]
    print(failed(lambda: made.__replace__(1)), failed(lambda: made.__replace__(nothing=1)), failed(lambda: cls.__replace__()), failed(lambda: cls.__replace__(1)))  # type: ignore[call-arg,no-untyped-call,type-var]
size = os.terminal_size((80, 24))
print(size, size.columns, size.lines, size.__replace__(columns=100), size.__replace__(), size.__replace__(lines=1).lines, type(size.__replace__()).__name__)
print(os.terminal_size([1, 2]), os.terminal_size(iter((3, 4))), os.terminal_size("ab"), os.terminal_size({5: 0, 6: 0}))  # type: ignore[arg-type]
full = os.stat_result(range(19))
print(full, full.st_atime, full.st_mtime, full.st_ctime, full.st_atime_ns, full.st_mtime_ns, full.st_ctime_ns, full.st_blksize, full.st_blocks, full.st_rdev, full[7], full[8], full[9], len(full))
print(full.__reduce__()[1], failed(lambda: full.__replace__()))  # type: ignore[no-untyped-call]
some = os.stat_result(range(10), {"st_atime": 1.5, "st_rdev": "r"})
print(some.st_atime, some.st_mtime, some.st_rdev, os.stat_result(range(11), {"st_mtime": 2}).st_atime, os.stat_result(range(11), {"st_mtime": 2}).st_mtime)
print(failed(lambda: os.stat_result(range(11), {"st_atime": 1})), failed(lambda: os.stat_result(range(19), {"st_atime": 1})), os.stat_result(range(19), {}).st_atime, os.stat_result(range(10), {}).st_atime)  # type: ignore[no-untyped-call]
print(os.stat_result(sequence=range(10), dict={"st_mtime": 7}).st_mtime)
partial = os.statvfs_result(range(10))
print(partial, partial.f_fsid, os.statvfs_result(range(11)).f_fsid, partial.f_namemax, partial.__replace__(f_fsid=9).f_fsid, partial.__replace__(f_bsize=9).f_bsize, partial.__replace__(f_bsize=9).f_fsid)


def raises_midway():  # type: ignore[no-untyped-def]
    yield 1
    raise ValueError


print(failed(lambda: os.terminal_size(raises_midway())))  # type: ignore[no-untyped-call]

# ---- the system calls, on a directory of the case's own
os.umask(0o022)
print(os.umask(0o022))
missing = base + "/missing"
print(attempt(os.mkdir, base, 0o755), attempt(os.mkdir, base), attempt(os.rmdir, missing), attempt(os.listdir, missing), attempt(os.stat, missing), attempt(os.lstat, missing), attempt(os.unlink, missing), attempt(os.remove, missing), attempt(os.chdir, missing), attempt(os.readlink, missing), attempt(os.open, missing, os.O_RDONLY))  # type: ignore[no-untyped-call]
print(os.access(base, os.F_OK), os.access(base, os.R_OK | os.W_OK | os.X_OK), os.access(missing, os.F_OK))
path = base + "/file"
fd = os.open(path, os.O_CREAT | os.O_RDWR | os.O_TRUNC, 0o640)
print(type(fd).__name__, os.write(fd, b"hello world"), os.write(fd, bytearray(b"!")), os.lseek(fd, 0, os.SEEK_SET), os.read(fd, 5), os.read(fd, 100), os.read(fd, 100), os.lseek(fd, -1, os.SEEK_END), os.read(fd, 0), os.isatty(fd), failed(lambda: os.fsync(fd)))  # type: ignore[no-untyped-call]
st = os.fstat(fd)
print(type(st).__name__, stat.S_ISREG(st.st_mode), oct(stat.S_IMODE(st.st_mode)), st.st_size, st.st_nlink, st.st_uid == os.getuid(), st.st_gid == os.getgid(), len(st), type(st.st_mtime).__name__, type(st.st_mtime_ns).__name__, type(st.st_blksize).__name__, type(st.st_blocks).__name__, type(st.st_rdev).__name__)
print(st[0] == st.st_mode, st[1] == st.st_ino, st[2] == st.st_dev, st[6] == st.st_size, st.st_mtime_ns // 1000000000 == st[8], st.st_atime_ns // 1000000000 == st[7], abs(st.st_mtime - st.st_mtime_ns / 1e9) < 1, repr(st).startswith("os.stat_result(st_mode="), st.__reduce__()[1][1]["st_mtime_ns"] == st.st_mtime_ns)  # type: ignore[index]
print(attempt(os.get_terminal_size, fd), attempt(os.read, fd, -1), attempt(os.lseek, fd, -1, os.SEEK_SET), attempt(os.fstat, 987654), attempt(os.close, 987654), attempt(os.read, 987654, 1), attempt(os.write, 987654, b"x"), attempt(os.lseek, 987654, 0, 0), attempt(os.fsync, 987654), os.isatty(987654), attempt(os.close, -1))  # type: ignore[no-untyped-call]
print(os.close(fd), attempt(os.close, fd))  # type: ignore[func-returns-value,no-untyped-call]
same_stat = os.stat(path)
print(same_stat == os.lstat(path), same_stat.st_size, os.stat(path, follow_symlinks=False).st_size, os.path.getsize(path), attempt(os.mkdir, path), attempt(os.mkdir, path + "/below"), attempt(os.listdir, path), attempt(os.rmdir, path), attempt(os.stat, path + "/below"), attempt(os.readlink, path), attempt(os.unlink, base), attempt(os.open, base, os.O_WRONLY))  # type: ignore[no-untyped-call]
link = base + "/link"
print(attempt(os.symlink, "file", link), attempt(os.symlink, "file", link), os.readlink(link), stat.S_ISLNK(os.lstat(link).st_mode), stat.S_ISREG(os.stat(link).st_mode), stat.S_ISLNK(os.stat(link, follow_symlinks=False).st_mode), os.path.islink(link), os.path.islink(path), os.stat(link).st_ino == same_stat.st_ino)  # type: ignore[no-untyped-call]
hard = base + "/hard"
print(attempt(os.link, path, hard), os.stat(path).st_nlink, os.path.samefile(path, hard), attempt(os.link, path, hard), attempt(os.link, missing, base + "/x"))  # type: ignore[no-untyped-call]
print(attempt(os.rename, hard, base + "/moved"), attempt(os.rename, missing, base + "/x"), attempt(os.replace, base + "/moved", base + "/moved2"), attempt(os.replace, missing, base + "/x"), attempt(os.unlink, base + "/moved2"), os.stat(path).st_nlink)  # type: ignore[no-untyped-call]
sub = base + "/sub"
print(attempt(os.mkdir, sub, 0o700), oct(stat.S_IMODE(os.stat(sub).st_mode)), stat.S_ISDIR(os.stat(sub).st_mode), sorted(os.listdir(base)), attempt(os.rmdir, base), attempt(os.rename, path, sub), attempt(os.rename, sub, path), attempt(os.rmdir, sub))  # type: ignore[no-untyped-call]
print(sorted(os.listdir(base)), type(os.listdir(base)).__name__)

# ---- str, bytes, PathLike, a file descriptor
class Path:
    def __init__(self, text):  # type: ignore[no-untyped-def]
        self.text = text

    def __fspath__(self):  # type: ignore[no-untyped-def]
        return self.text


class Both:
    def __index__(self):  # type: ignore[no-untyped-def]
        return 987654

    def __fspath__(self):  # type: ignore[no-untyped-def]
        return path


class Wrong:
    def __fspath__(self):  # type: ignore[no-untyped-def]
        return 1


raw = os.fsencode(base)
print(sorted(os.listdir(raw)), sorted(os.listdir(Path(base))), sorted(os.listdir(Path(raw))), os.stat(raw).st_ino == os.stat(base).st_ino, os.stat(Path(base)).st_ino == os.stat(base).st_ino, os.stat(Path(raw)).st_ino == os.stat(base).st_ino)  # type: ignore[no-untyped-call]
print(attempt(os.stat, os.fsencode(missing)), attempt(os.stat, Path(missing)), attempt(os.unlink, Path(os.fsencode(missing))), attempt(os.rename, os.fsencode(missing), os.fsencode(missing + "2")), attempt(os.listdir, Path(missing)))  # type: ignore[no-untyped-call]
print(attempt(os.stat, Both()), failed(lambda: os.stat(Wrong())), failed(lambda: os.lstat(Both())), failed(lambda: os.stat(1.5)), failed(lambda: os.stat(None)), failed(lambda: os.lstat(1)), failed(lambda: os.stat("a\0b")), failed(lambda: os.stat(b"a\0b")), failed(lambda: os.unlink("a\0b")), failed(lambda: os.mkdir(1)), failed(lambda: os.stat(2**70)), failed(lambda: os.stat(-(2**70))))  # type: ignore[arg-type,no-untyped-call]
print(failed(lambda: os.stat()), failed(lambda: os.stat("a", "b")), failed(lambda: os.stat(path=path, nothing=1)), failed(lambda: os.stat(path, path=path)), os.stat(path=path).st_size, os.lstat(path=path).st_size, os.open(path=path, flags=os.O_RDONLY) > 0, failed(lambda: os.rename(path)), failed(lambda: os.rename(path, 1)), failed(lambda: os.rename(path, base + "/m", 1)), failed(lambda: os.listdir(path, 1)), failed(lambda: os.getcwd(1)), failed(lambda: os.getpid(x=1)), failed(lambda: os.read(1)), failed(lambda: os.read(fd=1, length=1)))  # type: ignore[arg-type,call-arg,call-overload,misc,no-untyped-call]
print(failed(lambda: os.close("a")), failed(lambda: os.close(1.5)), failed(lambda: os.close(2**70)), failed(lambda: os.read("a", 1)), failed(lambda: os.read(0, "a")), failed(lambda: os.read(0, 2**70)), failed(lambda: os.write(0, "a")), failed(lambda: os.write("a", b"a")), failed(lambda: os.write(987654, 1)), failed(lambda: os.lseek(0, "a", 0)), failed(lambda: os.lseek(0, 0, "a")), failed(lambda: os.fstat("a")), failed(lambda: os.open(path, "a")), failed(lambda: os.open(path, os.O_RDONLY, "a")), failed(lambda: os.access(path, "a")), failed(lambda: os.mkdir(missing, "a")), failed(lambda: os.isatty("a")), failed(lambda: os.strerror("a")), failed(lambda: os.umask("a")), failed(lambda: os.urandom("a")), failed(lambda: os.urandom(-1)))  # type: ignore[arg-type,no-untyped-call]
print(attempt(os.fsync, 987654), failed(lambda: os.fsync(-1)), failed(lambda: os.fsync("a")))  # type: ignore[arg-type,no-untyped-call]


class FileLike:
    def fileno(self):  # type: ignore[no-untyped-def]
        return 987654


print(attempt(os.fsync, FileLike()), failed(lambda: os.close(FileLike())))  # type: ignore[arg-type,no-untyped-call]
bad_name = base + "/s\udc80"
print(attempt(os.mkdir, bad_name), [n.encode("utf-8", "surrogateescape") for n in sorted(os.listdir(base)) if n.startswith("s\udc80")], [n for n in os.listdir(raw) if n.startswith(b"s\x80")], attempt(os.rmdir, bad_name))  # type: ignore[no-untyped-call]
here = os.getcwd()
print(type(here).__name__, type(os.getcwdb()).__name__, os.fsencode(here) == os.getcwdb())
print(attempt(os.chdir, base), os.path.basename(os.getcwd()) == os.path.basename(base), os.path.basename(os.getcwdb()) == os.path.basename(raw), sorted(os.listdir()), sorted(os.listdir(None)), sorted(os.listdir(".")), sorted(os.listdir(b".")), os.path.getsize("file"), os.path.exists("file"), os.path.exists("nothing"), attempt(os.stat, "nothing"), shown(os.path.abspath("file")), shown(os.path.realpath("link")))  # type: ignore[no-untyped-call]
dir_fd = os.open(base, os.O_RDONLY)
print(sorted(os.listdir(dir_fd)), sorted(os.listdir(dir_fd)), stat.S_ISDIR(os.stat(dir_fd).st_mode), attempt(os.chdir, here), attempt(os.chdir, dir_fd), os.path.basename(os.getcwd()) == os.path.basename(base), attempt(os.chdir, here), os.close(dir_fd), attempt(os.chdir, dir_fd), attempt(os.listdir, 987654), attempt(os.stat, 987654))  # type: ignore[func-returns-value,no-untyped-call]
print(os.fspath("a"), os.fspath(b"a"), os.fspath(Path("p")), os.fspath(Path(b"p")), failed(lambda: os.fspath(1)), failed(lambda: os.fspath(Wrong())), failed(lambda: os.fspath()), os.fspath(path="q"), isinstance(Path("p"), os.PathLike), issubclass(Path, os.PathLike), isinstance(1, os.PathLike), failed(lambda: os.PathLike()), repr(os.PathLike))  # type: ignore[call-overload,misc,no-untyped-call]
print(os.fsencode("é"), os.fsdecode(b"\xc3\xa9"), repr(os.fsdecode(b"\xff")), os.fsencode("\udcff"), os.fsencode(Path("é")), os.fsdecode(Path(b"\xc3\xa9")), os.fsencode(b"b"), os.fsdecode("s"), failed(lambda: os.fsencode(1)), failed(lambda: os.fsdecode(1)))  # type: ignore[arg-type,no-untyped-call]

# ---- what the module says of the process and the system
print(os.getpid() > 0, os.getppid() >= 0, os.getuid() >= 0, os.geteuid() == os.getuid(), os.getgid() >= 0, os.getegid() == os.getgid(), os.getpid() == os.getpid())
print(type(os.urandom(0)).__name__, len(os.urandom(0)), len(os.urandom(16)), os.urandom(16) != os.urandom(16), type(os.cpu_count()).__name__)
print(os.strerror(2), os.strerror(13), os.strerror(0), os.strerror(99999))
name = os.uname()  # type: ignore[assignment]
print(type(name).__name__, name.sysname, name.sysname == name[0], len(name), repr(name).startswith("posix.uname_result(sysname='Linux', nodename="))  # type: ignore[attr-defined]
times = os.times()
print(type(times).__name__, len(times), [type(t).__name__ for t in times], times.user == times[0], times.elapsed == times[4], times.user >= 0)

# ---- posixpath over all of it
for args in (("a", "b"), ("a/", "b"), ("/a", "/b"), ("", "b"), ("a", ""), (b"a", b"b")):
    print(os.path.join(*args))
for p in ("", "a", "a/b", "/a/b/", "/", "//", "///", "//a", "a//b", "a.txt", "a/b.tar.gz", ".hidden", "a/.hidden", "..", "a/../b", "./a", "/a/./b/../c//", "../../a", "/../a", "//a/../b", "///a", b"a/b", b"/a/../b/", b""):
    print(repr(p), os.path.split(p), os.path.splitext(p), os.path.basename(p), os.path.dirname(p), os.path.normpath(p), os.path.isabs(p), os.path.splitdrive(p), os.path.splitroot(p))
print(os.path.commonpath(["/a/b", "/a/c"]), os.path.relpath("/a/b", "/a/c"), os.path.relpath("x", "x/y"), failed(lambda: os.path.commonpath([])), failed(lambda: os.path.commonpath(["/a", "b"])), failed(lambda: os.path.join(1)), failed(lambda: os.path.join("a", b"b")), failed(lambda: os.path.normpath(1)), failed(lambda: os.path.basename(1)), os.path.normpath(Path("a//b")), os.path.basename(Path("a/b")), failed(lambda: posix._path_normpath()), posix._path_normpath("a//b"), posix._path_normpath(b"a//b"), posix._path_normpath(""), posix._path_normpath(b""), posix._path_splitroot_ex("//a"), posix._path_splitroot_ex(b"///a"), posix._path_splitroot_ex(""), posix._path_splitroot_ex(Path("/a")))  # type: ignore[attr-defined,call-overload,no-untyped-call]
print(os.path.exists(path), os.path.exists(missing), os.path.exists(987654), os.path.exists("a\0b"), os.path.lexists(link), os.path.lexists(missing), os.path.isdir(base), os.path.isdir(path), os.path.isfile(path), os.path.isfile(base), os.path.isfile(missing), os.path.ismount("/"), os.path.ismount(base))
print(type(os.path.getmtime(path)).__name__, type(os.path.getatime(path)).__name__, type(os.path.getctime(path)).__name__, attempt(os.path.getmtime, missing), attempt(os.path.getsize, missing), os.path.samestat(os.stat(path), os.stat(link)), shown(os.path.realpath(link)), shown(os.path.realpath(missing)), shown(os.path.abspath(base + "/a/../b")), failed(lambda: os.path.realpath(missing, strict=True)))  # type: ignore[no-untyped-call]
os.environ["BELLA_HOME"] = "/home/somebody"
saved = os.environ.get("HOME")
os.environ["HOME"] = "/home/somebody"
print(os.path.expanduser("~"), os.path.expanduser("~/x"), os.path.expanduser("x"), os.path.expanduser(b"~/x"))
if saved is not None:
    os.environ["HOME"] = saved

# ---- what os builds
deep = base + "/d/e/f"
print(attempt(os.makedirs, deep), os.path.isdir(deep), attempt(os.makedirs, deep), attempt(os.makedirs, deep, exist_ok=True), attempt(os.makedirs, path + "/x"), attempt(os.makedirs, path, exist_ok=True))  # type: ignore[no-untyped-call]
print(attempt(os.renames, deep, base + "/g/h/i"), os.path.isdir(base + "/g/h/i"), os.path.exists(base + "/d"), attempt(os.removedirs, base + "/g/h/i"), os.path.exists(base + "/g"), os.path.exists(base))  # type: ignore[no-untyped-call]
print(type(os.environ).__name__, os.environ["BELLA_HOME"], "BELLA_HOME" in os.environ, "NOTHING_SET" in os.environ, os.environ.get("NOTHING_SET"), os.environ.get("NOTHING_SET", "d"), os.getenv("BELLA_HOME"), os.getenv("NOTHING_SET"), os.getenv("NOTHING_SET", "d"), os.environb[b"BELLA_HOME"], os.getenvb(b"BELLA_HOME"), failed(lambda: os.environ["NOTHING_SET"]), failed(lambda: os.environ[1]), failed(lambda: os.environb["s"]), failed(lambda: os.getenv(1)), failed(lambda: os.getenvb("s")))  # type: ignore[call-overload,index,no-untyped-call]
os.environ["BELLA_TEXT"] = "é\udcff"
print(repr(os.environ["BELLA_TEXT"]), os.environb[b"BELLA_TEXT"], os.environ.pop("BELLA_TEXT") == "é\udcff", "BELLA_TEXT" in os.environ, os.environ.setdefault("BELLA_SD", "1"), os.environ.setdefault("BELLA_SD", "2"), failed(lambda: os.environ.__setitem__("A", 1)), failed(lambda: os.environ.__setitem__(1, "A")), failed(lambda: os.environ.__delitem__("NOTHING_SET")), failed(lambda: os.environ.__setitem__("A\0", "b")), failed(lambda: os.environ.__setitem__("", "b")), failed(lambda: os.environ.__setitem__("A=B", "c")))  # type: ignore[assignment,index,no-untyped-call]
del os.environ["BELLA_SD"]
print("BELLA_SD" in os.environ, isinstance(os.environ, dict), type(os.environ.copy()).__name__, "BELLA_HOME" in os.environ.copy(), type(os.environ | {}).__name__, repr(os.environ).startswith("environ({"), type(iter(os.environ)).__name__, all(type(k) is str for k in os.environ))
print(failed(lambda: os.putenv("A")), failed(lambda: os.putenv("", "b")), failed(lambda: os.putenv("A=B", "c")), failed(lambda: os.putenv("A\0", "c")), failed(lambda: os.putenv(1, "c")), failed(lambda: os.unsetenv()), failed(lambda: os.unsetenv(1)), failed(lambda: os.unsetenv("")), failed(lambda: os.unsetenv("A=B")))  # type: ignore[arg-type,call-arg,no-untyped-call]
print(os.putenv("BELLA_PUT", "put"), "BELLA_PUT" in os.environ, os.reload_environ(), os.environ.get("BELLA_PUT"), os.unsetenv("BELLA_PUT"), os.environ.get("BELLA_PUT"), os.reload_environ(), os.environ.get("BELLA_PUT"), os.putenv(b"BELLA_PUT2", b"\xff"), os.reload_environ(), repr(os.environ.get("BELLA_PUT2")))  # type: ignore[func-returns-value]
print(failed(lambda: os.register_at_fork()), failed(lambda: os.register_at_fork(before=1)), failed(lambda: os.register_at_fork(print)), failed(lambda: os.register_at_fork(nothing=print)), os.register_at_fork(before=print), os.register_at_fork(after_in_child=print, after_in_parent=print))  # type: ignore[arg-type,call-arg,func-returns-value,no-untyped-call]

# ---- leave nothing behind
print(attempt(os.unlink, link), attempt(os.unlink, path), attempt(os.rmdir, base), os.path.exists(base))  # type: ignore[no-untyped-call]
os.environ.clear()
print(len(os.environ), dict(os.environ), os.reload_environ(), len(os.environ))  # type: ignore[func-returns-value]
