# clause: C-7-58
# spec: section 7
# status: P1
# source: dialect specification section 7 (os), Modules/posixmodule.c (os.scandir, DirEntry, ScandirIterator), Lib/shutil.py (rmtree over a directory descriptor)
"""os.scandir: an iterator of DirEntry objects over a directory given by a str, bytes, a path-like object, a descriptor or
nothing; each entry's name and path (bytes for a bytes path, the name alone under a descriptor), its inode, is_dir, is_file
and is_symlink with and without following a link, stat, cached per entry and fetched through the descriptor when there is one,
__fspath__ and repr; the iterator's close, its context manager, what it yields once closed or exhausted, and the ResourceWarning
of one dropped unfinished; the errors of a missing directory and of a file; and what shutil.rmtree needs beside it: lstat, open,
unlink and rmdir with dir_fd, with which a TemporaryDirectory cleans up after itself."""
# ruff: noqa: E501, PTH
import os
import shutil
import stat
import sys
import tempfile
import warnings
from collections.abc import Callable


def m(f: Callable[[], object]) -> str:
    try:
        return repr(f())
    except OSError as e:
        return type(e).__name__ + ": " + repr((e.errno, e.strerror, os.path.basename(str(e.filename)) if isinstance(e.filename, (str, bytes)) else e.filename))
    except Exception as e:
        return type(e).__name__ + ": " + str(e)


def shown(entry: os.DirEntry[str] | os.DirEntry[bytes], root: str) -> tuple[object, ...]:
    path = os.fsdecode(entry.path)
    return (entry.name, path.removeprefix(root), entry.is_dir(), entry.is_file(), entry.is_symlink(), entry.is_dir(follow_symlinks=False), entry.is_file(follow_symlinks=False),
            entry.is_junction(), entry.inode() == os.lstat(os.path.join(root, os.fsdecode(entry.name))).st_ino, os.fspath(entry) == entry.path, repr(entry))


with tempfile.TemporaryDirectory() as root:
    os.mkdir(os.path.join(root, "dir"))
    os.mkdir(os.path.join(root, "dir", "inner"))
    for name, text in (("a.txt", "a"), ("b.txt", "bb"), ("zażółć.txt", "ccc"), (os.path.join("dir", "in.txt"), "dddd")):
        with open(os.path.join(root, name), "w", encoding="utf-8") as f:
            f.write(text)
    os.symlink("a.txt", os.path.join(root, "link-to-file"))
    os.symlink("dir", os.path.join(root, "link-to-dir"))
    os.symlink("nowhere", os.path.join(root, "link-to-nothing"))

    # the entries, by every kind of path
    with os.scandir(root) as it:
        print("iterator:", type(it).__name__, type(it).__module__, iter(it) is it, m(lambda: type(it)()), m(lambda: os.DirEntry()), os.DirEntry.__name__, os.DirEntry.__module__)
        entries = sorted(it, key=lambda e: e.name)
    for entry in entries:
        print("str:", shown(entry, root))
    print("bytes:", [(e.name, e.path.removeprefix(os.fsencode(root)), e.is_dir()) for e in sorted(os.scandir(os.fsencode(root)), key=lambda e: e.name)][:3])
    print("path-like:", sorted(e.name for e in os.scandir(entries[3])), [e.path.removeprefix(root) for e in os.scandir(os.path.join(root, "dir", ""))])
    here = os.getcwd()
    os.chdir(root)
    print("default:", sorted((e.name, e.path) for e in os.scandir())[:2], sorted((e.name, e.path) for e in os.scandir("."))[:2], sorted(e.path for e in os.scandir(None))[:1])
    os.chdir(here)
    fd = os.open(root, os.O_RDONLY)
    with os.scandir(fd) as it:
        by_fd = sorted(it, key=lambda e: e.name)
    print("descriptor:", [(e.name, e.path, e.is_dir(), e.is_symlink(), e.stat().st_size if e.is_file() else None, e.stat(follow_symlinks=False).st_ino == e.inode()) for e in by_fd if e.name != "link-to-nothing"])
    print("descriptor, a dangling link:", [(m(e.stat), e.is_file(), e.is_dir(), e.is_symlink(), stat.S_ISLNK(e.stat(follow_symlinks=False).st_mode)) for e in by_fd if e.name == "link-to-nothing"])
    print("the descriptor is still open and at its start:", sorted(os.listdir(fd))[:2], os.fstat(fd).st_ino == os.stat(root).st_ino)

    # stat: cached per entry, the link's own or its target's
    a, link, dangling = entries[0], entries[4], entries[5]
    print("stat:", a.stat() is a.stat(), a.stat(follow_symlinks=False) is a.stat(), a.stat().st_size, link.stat().st_size, link.stat() is link.stat(follow_symlinks=False),
          stat.S_ISLNK(link.stat(follow_symlinks=False).st_mode), stat.S_ISREG(link.stat().st_mode), m(dangling.stat), dangling.is_file(), dangling.is_dir(), dangling.is_symlink(), type(a.stat()).__name__)
    os.unlink(os.path.join(root, "b.txt"))
    b = entries[1]
    print("an entry whose file is gone:", b.name, m(b.stat), m(lambda: b.stat(follow_symlinks=False)), b.is_symlink(), b.inode() > 0)
    print("members:", m(lambda: setattr(a, "name", "x")), m(lambda: setattr(a, "path", "x")), m(lambda: a.stat(True)), m(lambda: a.is_dir(True)), m(lambda: a.is_dir(follow=True)), m(lambda: a.inode(1)),  # type: ignore[call-arg]
          m(lambda: a.is_symlink(1)), a == a, a == entries[0], hash(a) == hash(a), m(lambda: os.DirEntry[str]), sorted(n for n in dir(a) if not n.startswith("_")))  # type: ignore[call-arg]

    # the iterator: closing, exhausting, dropping
    it = os.scandir(root)
    first = next(it)
    print("close:", it.close(), m(lambda: next(it)), it.close(), list(it), first.name in os.listdir(root))  # type: ignore[func-returns-value]
    it = os.scandir(root)
    print("exhausted:", len(list(it)), list(it), m(lambda: next(it)), it.close())  # type: ignore[func-returns-value]
    with os.scandir(root) as it:
        print("context:", it.__enter__() is it, it.__exit__(None, None, None), m(lambda: next(it)))  # type: ignore[func-returns-value]
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        started = os.scandir(root)
        next(started)
        del started
        os.scandir(root)                         # never started: unclosed all the same
        finished = os.scandir(root)
        list(finished)
        del finished                             # exhausted: closed
    print("dropped:", [(w.category.__name__, str(w.message).split(" <")[0], str(w.message).split(" <")[1].split(" object")[0]) for w in caught])

    # errors
    print("errors:", m(lambda: os.scandir(os.path.join(root, "missing"))), m(lambda: os.scandir(os.path.join(root, "a.txt"))), m(lambda: os.scandir(1.5)), m(lambda: os.scandir(root, root)),  # type: ignore[call-overload]
          m(lambda: os.scandir(path=root).close()), m(lambda: os.scandir(-1)), m(lambda: os.scandir("a\0b")), m(lambda: os.scandir(10 ** 30)))
    os.close(fd)
    print("a closed descriptor:", m(lambda: os.scandir(fd)))

    # dir_fd, as shutil.rmtree uses it; then the tree goes
    top = os.open(root, os.O_RDONLY)
    print("dir_fd:", os.lstat("a.txt", dir_fd=top).st_size, stat.S_ISLNK(os.lstat("link-to-file", dir_fd=top).st_mode), os.stat("link-to-file", dir_fd=top).st_size,
          os.stat("link-to-file", dir_fd=top, follow_symlinks=False).st_size == os.lstat("link-to-file", dir_fd=top).st_size, m(lambda: os.stat("missing", dir_fd=top)), m(lambda: os.lstat("a.txt", dir_fd=-1)))
    inner = os.open("dir", os.O_RDONLY, dir_fd=top)
    print("open:", sorted(os.listdir(inner)), m(lambda: os.open("missing", os.O_RDONLY, dir_fd=top)))
    os.unlink("in.txt", dir_fd=inner)
    os.rmdir("inner", dir_fd=inner)
    print("unlink and rmdir:", os.listdir(inner), m(lambda: os.unlink("in.txt", dir_fd=inner)), m(lambda: os.rmdir("inner", dir_fd=inner)), m(lambda: os.rmdir("a.txt", dir_fd=top)), m(lambda: os.unlink("dir", dir_fd=top)))
    os.close(inner)
    os.close(top)
    shutil.rmtree(os.path.join(root, "dir"))
    print("rmtree:", sorted(os.listdir(root)), shutil.rmtree.avoids_symlink_attacks, m(lambda: shutil.rmtree(os.path.join(root, "link-to-file"))))
print("after the with:", os.path.exists(root), sys.exc_info()[0])
