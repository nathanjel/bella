# clause: C-7-10
# spec: section 7
# status: P1
# source: dialect specification section 7, Files and OS (os, os.path, pathlib, io, shutil, tempfile, glob, fnmatch, stat, errno)
"""Files and OS inside a temporary directory; only names relative to it are printed."""
import errno
import fnmatch
import glob
import io
import os
import pathlib
import shutil
import stat
import tempfile

with tempfile.TemporaryDirectory() as tmp:
    root = pathlib.Path(tmp)
    (root / "src" / "pkg").mkdir(parents=True)
    (root / "src" / "a.txt").write_text("alpha\n", encoding="utf-8")
    (root / "src" / "b.py").write_bytes(b"print(1)\n")
    (root / "src" / "pkg" / "c.txt").write_text("gamma", encoding="utf-8")
    print(sorted(os.listdir(root / "src")), sorted(p.name for p in (root / "src").iterdir()))
    print(sorted(str(p.relative_to(root)) for p in root.rglob("*.txt")))
    print(sorted(os.path.relpath(p, tmp) for p in glob.glob(os.path.join(tmp, "src", "*"))))
    print(sorted(glob.glob("**/*.txt", root_dir=tmp, recursive=True)), fnmatch.filter(["a.txt", "b.py", "c.TXT"], "*.txt"))
    shutil.copytree(root / "src", root / "copy")
    shutil.copy(root / "src" / "a.txt", root / "copy" / "a2.txt")
    shutil.move(root / "copy" / "b.py", root / "copy" / "pkg" / "b.py")
    walked = [(os.path.relpath(d, tmp), sorted(dirs), sorted(files)) for d, dirs, files in os.walk(root / "copy")]
    print(sorted(walked))
    info = os.stat(root / "src" / "a.txt")
    print(info.st_size, stat.S_ISREG(info.st_mode), stat.S_ISDIR(os.stat(root / "src").st_mode), stat.filemode(stat.S_IFDIR | 0o755))
    p = root / "src" / "a.txt"
    print(p.suffix, p.stem, p.with_suffix(".md").name, p.parent.name, p.read_text(encoding="utf-8").strip(), p.exists())
    try:
        open(root / "missing.txt", encoding="utf-8")  # noqa: SIM115  # the error is the point
    except FileNotFoundError as exc:
        print("missing:", type(exc).__name__, exc.errno == errno.ENOENT, os.path.basename(str(exc.filename)))
    with open(root / "log.txt", "a+", encoding="utf-8") as f:
        f.write("one\ntwo\n")
        f.seek(0)
        print(f.readlines(), f.tell())
    shutil.rmtree(root / "copy")
    print("after rmtree:", sorted(os.listdir(tmp)))
print(os.path.join("a", "b", "../c"), os.path.normpath("a/b/../c"), os.path.splitext("x.tar.gz"), os.path.basename("/x/y.z"))
print(pathlib.PurePosixPath("/a/b/c.txt").parts, pathlib.PurePath("a") / "b", os.sep, os.extsep, errno.errorcode[errno.EEXIST])
b = io.BytesIO()
b.write(b"abc")
s = io.StringIO("line1\nline2\n")
print(b.getvalue(), s.readline(), list(s), io.TextIOWrapper(io.BytesIO("é".encode()), encoding="utf-8").read())
