# clause: C-7-68
# spec: section 7
# status: P1
# source: dialect specification section 7 (os), Modules/posixmodule.c (os_statvfs_impl, os_fstatvfs_impl, _pystatvfs_fromstructstatvfs, conv_confname, os_sysconf_impl, os_confstr_impl, os_pathconf_impl, os_fpathconf_impl)
"""What a file system says of itself (statvfs by name or descriptor, fstatvfs) and the limits the system is configured with:
sysconf, confstr, pathconf and fpathconf, each by a name of its table or by the number, the table being read when the function
is called; what they refuse, and what their OSError carries."""
# ruff: noqa: E501, PTH
# The numbers are the machine's and the file system's own: what is printed is what holds on every one of them (a kind, a
# relation, the few limits that Linux fixes), never a count of blocks or of processors.
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


class Fileno:
    def __init__(self, fd: int) -> None:
        self.fd = fd

    def fileno(self) -> int:
        return self.fd


def steady(st: os.statvfs_result) -> tuple[int, int, int, int, int]:
    """What does not move while the program runs: the sizes, the flags, the longest name, the file system's id."""
    return st.f_bsize, st.f_frsize, st.f_flag, st.f_namemax, st.f_fsid


def main() -> None:
    d = tempfile.mkdtemp()
    os.chdir(d)
    with open("f", "wb") as f:
        f.write(b"x")
    fd = os.open("f", os.O_RDONLY)
    top = os.open(d, os.O_RDONLY)
    r, w = os.pipe()

    st = os.statvfs(".")
    print("statvfs:", type(st).__name__, type(st).__module__, len(st), st.n_fields, st.n_sequence_fields, all(type(v) is int for v in st), type(st.f_fsid).__name__, st.f_bsize > 0, st.f_frsize > 0, st.f_blocks >= st.f_bfree >= 0,
          st.f_bfree >= st.f_bavail, st.f_files >= st.f_ffree >= 0, st.f_namemax == os.pathconf(".", "PC_NAME_MAX"), st[0] == st.f_bsize, st[9] == st.f_namemax, m(lambda: st[10]), repr(st).startswith("os.statvfs_result(f_bsize="),
          repr(st).count("="), "f_fsid" in repr(st))
    print("the same file system:", steady(os.statvfs(d)) == steady(st), steady(os.statvfs(b".")) == steady(st), steady(os.statvfs(path="f")) == steady(st), steady(os.statvfs(top)) == steady(st), steady(os.fstatvfs(fd)) == steady(st),
          steady(os.fstatvfs(Index(top))) == steady(st), type(os.fstatvfs(fd)) is type(st), bool(st.f_flag & os.ST_RDONLY))  # type: ignore[arg-type]
    print("statvfs refuses:", m(lambda: os.statvfs("missing")), m(lambda: os.statvfs(b"missing")), m(lambda: os.statvfs(987)), m(lambda: os.statvfs()), m(lambda: os.statvfs(1.5)), m(lambda: os.statvfs(".", 1)), m(lambda: os.statvfs(name=".")),  # type: ignore[call-arg, arg-type]
          m(lambda: os.fstatvfs(987)), m(lambda: os.fstatvfs("f")), m(lambda: os.fstatvfs()), m(lambda: os.fstatvfs(fd=fd)), m(lambda: os.fstatvfs(1.5)), m(lambda: os.fstatvfs(Fileno(fd))))  # type: ignore[arg-type, call-arg]

    # sysconf
    print("sysconf:", type(os.sysconf("SC_PAGE_SIZE")).__name__, os.sysconf("SC_PAGE_SIZE") == os.sysconf("SC_PAGESIZE") == os.sysconf(os.sysconf_names["SC_PAGE_SIZE"]), os.sysconf("SC_PAGE_SIZE") > 0, os.sysconf("SC_CLK_TCK"),
          1 <= os.sysconf("SC_NPROCESSORS_ONLN") <= os.sysconf("SC_NPROCESSORS_CONF"), os.sysconf(Index(os.sysconf_names["SC_CLK_TCK"])), os.sysconf("SC_OPEN_MAX") > 3, os.sysconf("SC_ARG_MAX") > 4096)  # type: ignore[arg-type]
    os.sysconf_names["THE_PROGRAMS_OWN"] = os.sysconf_names["SC_CLK_TCK"]
    os.sysconf_names["NOT_A_NUMBER"] = "x"  # type: ignore[assignment]
    print("the table is read at the call:", os.sysconf("THE_PROGRAMS_OWN"), m(lambda: os.sysconf("NOT_A_NUMBER")))
    del os.sysconf_names["THE_PROGRAMS_OWN"], os.sysconf_names["NOT_A_NUMBER"]
    print("sysconf refuses:", m(lambda: os.sysconf("THE_PROGRAMS_OWN")), m(lambda: os.sysconf("nope")), m(lambda: os.sysconf("")), m(lambda: os.sysconf(1.5)), m(lambda: os.sysconf(None)), m(lambda: os.sysconf(b"SC_CLK_TCK")),  # type: ignore[arg-type]
          m(lambda: os.sysconf(99999)), m(lambda: os.sysconf(-5)), m(lambda: os.sysconf(2 ** 40)), m(lambda: os.sysconf()), m(lambda: os.sysconf(1, 2)), m(lambda: os.sysconf(name="SC_CLK_TCK")))  # type: ignore[call-arg]

    # confstr
    path = os.confstr("CS_PATH")
    print("confstr:", type(path).__name__, path == os.confstr(os.confstr_names["CS_PATH"]), "/bin" in str(path), str(os.confstr("CS_GNU_LIBC_VERSION")).startswith("glibc "), repr(os.confstr("CS_LFS_CFLAGS")),
          str(os.confstr("CS_GNU_LIBPTHREAD_VERSION")).startswith("NPTL "), m(lambda: os.confstr("nope")), m(lambda: os.confstr(99999)), m(lambda: os.confstr(-1)), m(lambda: os.confstr(None)), m(lambda: os.confstr(1.5)),  # type: ignore[arg-type]
          m(lambda: os.confstr()), m(lambda: os.confstr(name="CS_PATH")), m(lambda: os.confstr(2 ** 40)))  # type: ignore[call-arg]

    # pathconf and fpathconf
    print("pathconf:", os.pathconf(".", "PC_NAME_MAX"), os.pathconf(".", "PC_PATH_MAX"), os.pathconf("f", os.pathconf_names["PC_NAME_MAX"]), os.pathconf(top, "PC_NAME_MAX"), os.pathconf(b"f", "PC_PATH_MAX"), os.pathconf(name="PC_NAME_MAX", path="."),
          type(os.pathconf(".", "PC_LINK_MAX")).__name__, os.pathconf(r, "PC_PIPE_BUF"), os.fpathconf(top, "PC_NAME_MAX"), os.fpathconf(fd, Index(os.pathconf_names["PC_PATH_MAX"])), os.fpathconf(r, "PC_PIPE_BUF"),  # type: ignore[arg-type]
          os.fpathconf(Fileno(top), "PC_NAME_MAX"))  # type: ignore[arg-type]
    print("pathconf refuses:", m(lambda: os.pathconf("missing", "PC_NAME_MAX")), m(lambda: os.pathconf(".", 99999)), m(lambda: os.pathconf("missing", 99999)), m(lambda: os.pathconf(".", "nope")), m(lambda: os.pathconf(987, "PC_NAME_MAX")),
          m(lambda: os.pathconf(987, 99999)), m(lambda: os.pathconf(".", 1.5)), m(lambda: os.pathconf(1.5, "PC_NAME_MAX")), m(lambda: os.pathconf(".")), m(lambda: os.pathconf(".", "PC_NAME_MAX", 1)),  # type: ignore[arg-type, call-arg]
          m(lambda: os.fpathconf(987, "PC_NAME_MAX")), m(lambda: os.fpathconf(top, 99999)), m(lambda: os.fpathconf(top, "nope")), m(lambda: os.fpathconf("f", "PC_NAME_MAX")), m(lambda: os.fpathconf(top)),  # type: ignore[arg-type, call-arg]
          m(lambda: os.fpathconf(fd=top, name="PC_NAME_MAX")), m(lambda: os.fpathconf(top, None)))  # type: ignore[call-arg, arg-type]

    for descriptor in (fd, top, r, w):
        os.close(descriptor)
    os.chdir("/")
    os.unlink(os.path.join(d, "f"))
    os.rmdir(d)


if __name__ == "__main__":
    main()
