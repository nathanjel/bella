# clause: C-7-64
# spec: section 7
# status: P1
# source: dialect specification section 7 (os), Modules/posixmodule.c (os_mkdir_impl, internal_rename, os_access_impl, os_readlink_impl, os_symlink_impl, os_link_impl, dir_fd_converter)
"""dir_fd for the functions of os that make, name and ask about a directory's entries: mkdir, rename and replace (a descriptor
for each side), access (with effective_ids and follow_symlinks, which go the same way), readlink, symlink and link (a descriptor
for each side, and the link itself or what it points to). A relative name is looked up under the descriptor's directory and an
absolute one is not; a descriptor that is no directory's, or is closed, or is no integer, says so; and an OSError carries the
names as they were given."""
# ruff: noqa: E501, PTH
import os
import stat
import tempfile
from collections.abc import Callable


def m(f: Callable[[], object]) -> str:
    try:
        return repr(f())
    except OSError as e:
        return type(e).__name__ + ": " + repr((e.errno, e.strerror, e.filename if isinstance(e.filename, (str, bytes)) and not os.path.isabs(e.filename) else type(e.filename).__name__, e.filename2))
    except Exception as e:
        return type(e).__name__


def tree(root: str) -> list[tuple[str, str]]:
    out = []
    for where, dirs, files in os.walk(root):
        for name in dirs + files:
            path = os.path.join(where, name)
            kind = "link to " + os.readlink(path) if os.path.islink(path) else "dir" if os.path.isdir(path) else "file"
            out.append((os.path.relpath(path, root), kind))
    return sorted(out)


def main() -> None:
    d = tempfile.mkdtemp()
    os.mkdir(os.path.join(d, "sub"))
    os.mkdir(os.path.join(d, "elsewhere"))
    with open(os.path.join(d, "f"), "w", encoding="utf-8") as f:
        f.write("0123")
    top = os.open(d, os.O_RDONLY)
    sub = os.open(os.path.join(d, "sub"), os.O_RDONLY)
    other = os.open(os.path.join(d, "elsewhere"), os.O_RDONLY)
    a_file = os.open(os.path.join(d, "f"), os.O_RDONLY)
    closed = os.open(d, os.O_RDONLY)
    os.close(closed)
    os.chdir("/")                                # a relative name finds nothing here: only the descriptor leads to it

    # mkdir
    print("mkdir:", m(lambda: os.mkdir("made", dir_fd=top)), m(lambda: os.mkdir("deep", 0o700, dir_fd=sub)), m(lambda: os.mkdir(b"bytes", dir_fd=top)), m(lambda: os.mkdir(path="named", mode=0o750, dir_fd=top)),
          oct(stat.S_IMODE(os.stat("deep", dir_fd=sub).st_mode)), m(lambda: os.mkdir("made", dir_fd=top)), m(lambda: os.mkdir(b"bytes", dir_fd=top)), m(lambda: os.mkdir("no/such", dir_fd=top)),
          m(lambda: os.mkdir("under a file", dir_fd=a_file)), m(lambda: os.mkdir("closed", dir_fd=closed)), m(lambda: os.mkdir(os.path.join(d, "absolute"), dir_fd=a_file)))
    print("mkdir's dir_fd:", m(lambda: os.mkdir("x", dir_fd="top")), m(lambda: os.mkdir("x", dir_fd=1.5)), m(lambda: os.mkdir("x", dir_fd=2 ** 40)), m(lambda: os.mkdir("x", dir_fd=-(2 ** 40))), m(lambda: os.mkdir("x", dir_fd=-1)),  # type: ignore[arg-type]
          m(lambda: os.mkdir("x", 0o777, top)), m(lambda: os.mkdir("x", src_dir_fd=top)))  # type: ignore[call-arg]
    print(tree(d))

    # rename and replace
    print("rename:", m(lambda: os.rename("f", "g", src_dir_fd=top, dst_dir_fd=top)), m(lambda: os.rename("g", "moved", src_dir_fd=top, dst_dir_fd=other)), m(lambda: os.replace("moved", "f", src_dir_fd=other, dst_dir_fd=top)),
          m(lambda: os.rename(b"f", b"g", src_dir_fd=top, dst_dir_fd=top)), m(lambda: os.replace(src="g", dst="f", dst_dir_fd=top, src_dir_fd=top)))
    os.chdir(os.path.join(d, "elsewhere"))
    print("one side:", m(lambda: os.rename("f", "here", src_dir_fd=top)), os.listdir("."), m(lambda: os.rename("here", "f", dst_dir_fd=top)), os.listdir("."), m(lambda: os.replace("made", "kept", src_dir_fd=top)),
          m(lambda: os.replace("kept", "made", dst_dir_fd=top)), m(lambda: os.mkdir("in the working directory", dir_fd=None)), m(lambda: os.rename("in the working directory", "renamed there", src_dir_fd=None, dst_dir_fd=None)),
          m(lambda: os.readlink("nothing", dir_fd=None)), os.access("renamed there", os.F_OK, dir_fd=None), sorted(os.listdir(".")))
    os.chdir("/")
    print("rename fails:", m(lambda: os.rename("nothing", "x", src_dir_fd=top, dst_dir_fd=top)), m(lambda: os.rename(b"nothing", b"x", src_dir_fd=top, dst_dir_fd=top)), m(lambda: os.rename("f", "x", src_dir_fd=a_file, dst_dir_fd=top)),
          m(lambda: os.rename("f", "x", src_dir_fd=top, dst_dir_fd=closed)), m(lambda: os.replace("f", "sub", src_dir_fd=top, dst_dir_fd=top)), m(lambda: os.rename("made", "sub", src_dir_fd=top, dst_dir_fd=top)),
          m(lambda: os.rename("f", "x", dir_fd=top)), m(lambda: os.rename("f", "x", src_dir_fd="top")), m(lambda: os.rename("f", "x", top, top)))  # type: ignore[call-arg, arg-type]
    print(tree(d))

    # symlink and readlink
    print("symlink:", m(lambda: os.symlink("f", "ln", dir_fd=top)), m(lambda: os.symlink("nowhere", "dangling", dir_fd=top)), m(lambda: os.symlink("sub", "to a dir", True, dir_fd=top)), m(lambda: os.symlink(b"f", b"bytes ln", dir_fd=top)),
          m(lambda: os.symlink(src="../f", dst="up", target_is_directory=False, dir_fd=sub)), m(lambda: os.symlink("f", "ln", dir_fd=top)), m(lambda: os.symlink("f", "x", dir_fd=a_file)), m(lambda: os.symlink("f", "x", dir_fd=closed)),
          m(lambda: os.symlink("f", "x", dir_fd="top")), m(lambda: os.symlink("f", os.path.join(d, "absolute ln"), dir_fd=a_file)))  # type: ignore[arg-type]
    print("readlink:", m(lambda: os.readlink("ln", dir_fd=top)), m(lambda: os.readlink(b"ln", dir_fd=top)), m(lambda: os.readlink("dangling", dir_fd=top)), m(lambda: os.readlink("up", dir_fd=sub)), m(lambda: os.readlink(path="bytes ln", dir_fd=top)),
          m(lambda: os.readlink("f", dir_fd=top)), m(lambda: os.readlink("nothing", dir_fd=top)), m(lambda: os.readlink("ln", dir_fd=a_file)), m(lambda: os.readlink("ln", dir_fd=closed)), m(lambda: os.readlink("ln", dir_fd=1.5)),  # type: ignore[arg-type]
          m(lambda: os.readlink(os.path.join(d, "ln"), dir_fd=a_file)), m(lambda: os.readlink("ln")))

    # access: under a directory, by the effective ids, and of a link itself
    print("access:", os.access("f", os.R_OK, dir_fd=top), os.access("f", os.F_OK, dir_fd=top), os.access("f", os.X_OK, dir_fd=top), os.access("nothing", os.F_OK, dir_fd=top), os.access("f", os.F_OK), os.access("sub", os.R_OK | os.X_OK, dir_fd=top),
          os.access("f", os.R_OK, dir_fd=a_file), os.access("f", os.R_OK, dir_fd=closed), os.access(os.path.join(d, "f"), os.R_OK, dir_fd=a_file), os.access(b"f", os.R_OK, dir_fd=top), os.access(path="f", mode=os.R_OK, dir_fd=top))
    print("effective ids:", os.access("f", os.R_OK, dir_fd=top, effective_ids=True), os.access("nothing", os.R_OK, dir_fd=top, effective_ids=True), os.access(os.path.join(d, "f"), os.R_OK, effective_ids=True),
          os.access(os.path.join(d, "f"), os.X_OK, effective_ids=True), os.access(os.path.join(d, "f"), os.R_OK, effective_ids=False), os.access("f", os.F_OK, dir_fd=top, effective_ids=1))  # type: ignore[arg-type]
    print("a link itself:", os.access("dangling", os.F_OK, dir_fd=top), os.access("dangling", os.F_OK, dir_fd=top, follow_symlinks=False), os.access(os.path.join(d, "dangling"), os.F_OK, follow_symlinks=False),
          os.access(os.path.join(d, "dangling"), os.F_OK), os.access("ln", os.R_OK, dir_fd=top, follow_symlinks=False), os.access("nothing", os.F_OK, dir_fd=top, follow_symlinks=False),
          os.access("dangling", os.F_OK, dir_fd=top, effective_ids=True, follow_symlinks=False))
    print("access refuses:", m(lambda: os.access("f", os.R_OK, dir_fd="top")), m(lambda: os.access("f", os.R_OK, dir_fd=2 ** 40)), m(lambda: os.access("f", os.R_OK, top)), m(lambda: os.access("f")))  # type: ignore[arg-type, call-arg]

    # link: a descriptor for each side, and the link itself or what it points to
    print("link:", m(lambda: os.link("f", "hard", src_dir_fd=top, dst_dir_fd=other)), os.stat("f", dir_fd=top).st_nlink, os.path.samefile(os.path.join(d, "f"), os.path.join(d, "elsewhere", "hard")),
          m(lambda: os.link("ln", "followed", src_dir_fd=top, dst_dir_fd=top)), m(lambda: os.link("ln", "the link", src_dir_fd=top, dst_dir_fd=top, follow_symlinks=False)),
          m(lambda: os.link("ln", "followed too", src_dir_fd=top, dst_dir_fd=top, follow_symlinks=True)), m(lambda: os.link(b"f", b"bytes hard", src_dir_fd=top, dst_dir_fd=sub)),
          m(lambda: os.link(src="f", dst="named hard", dst_dir_fd=sub, src_dir_fd=top)), os.stat("f", dir_fd=top).st_nlink)
    os.chdir(os.path.join(d, "elsewhere"))
    print("one side:", m(lambda: os.link("f", "from top", src_dir_fd=top)), m(lambda: os.link("hard", "to top", dst_dir_fd=top)), m(lambda: os.link("hard", "plain")), m(lambda: os.link("hard", "plain, the link", follow_symlinks=False)),
          sorted(os.listdir(".")))
    os.chdir("/")
    print("link fails:", m(lambda: os.link("nothing", "x", src_dir_fd=top, dst_dir_fd=top)), m(lambda: os.link("f", "hard", src_dir_fd=top, dst_dir_fd=other)), m(lambda: os.link("dangling", "x", src_dir_fd=top, dst_dir_fd=top)),
          m(lambda: os.link("f", "x", src_dir_fd=a_file, dst_dir_fd=top)), m(lambda: os.link("f", "x", src_dir_fd=top, dst_dir_fd=closed)), m(lambda: os.link("sub", "x", src_dir_fd=top, dst_dir_fd=top)),
          m(lambda: os.link("f", "x", dir_fd=top)), m(lambda: os.link("f", "x", src_dir_fd=1.5)), m(lambda: os.link("f", "x", top, top)))  # type: ignore[call-arg, arg-type]
    print(tree(d))

    for fd in (top, sub, other, a_file):
        os.close(fd)
    for where, dirs, files in os.walk(d, topdown=False):
        for name in files:
            os.unlink(os.path.join(where, name))
        for name in dirs:
            path = os.path.join(where, name)
            if os.path.islink(path):
                os.unlink(path)
            else:
                os.rmdir(path)
    os.rmdir(d)


if __name__ == "__main__":
    main()
