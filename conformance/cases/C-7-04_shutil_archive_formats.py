# clause: C-7-04
# spec: section 7
# status: P2+
# source: review log RL-59 (shutil's built-in archive formats import tarfile or zipfile and are [P2+])
"""make_archive and unpack_archive with a built-in format. Phase 1 refuses them with the
milestone-naming error (the functions they call are in the lock's unsupported_functions)."""
import os
import shutil
import tempfile

with tempfile.TemporaryDirectory() as tmp:
    src = os.path.join(tmp, "src")
    os.mkdir(src)
    with open(os.path.join(src, "a.txt"), "w", encoding="utf-8") as f:
        f.write("hello")
    archive = shutil.make_archive(os.path.join(tmp, "out"), "zip", root_dir=src)
    print(os.path.basename(archive), os.path.getsize(archive) > 0)
    dest = os.path.join(tmp, "dest")
    shutil.unpack_archive(archive, dest)
    with open(os.path.join(dest, "a.txt"), encoding="utf-8") as f:
        print(sorted(os.listdir(dest)), f.read())
