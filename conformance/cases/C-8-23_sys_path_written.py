# clause: C-8-23
# spec: section 8
# status: P1
# source: the author's decision of 2026-11-28 (Question 56): writes to sys.path, and the search an import makes after one
"""sys.path written: the program's own directory inserted again, entries before it that hold nothing for the name (an
empty directory, one that does not exist, one sys.path_importer_cache says has no finder), an entry that is no str, and
an empty directory appended; the import after them finds what CPython's search finds, and a module nothing on the list
holds is a ModuleNotFoundError. The list put back as it was."""
import importlib
import os
import sys
import tempfile

here = os.path.dirname(os.path.abspath(__file__))
start = list(sys.path)
print("json" in sys.modules, sys.path[0] == here)
with tempfile.TemporaryDirectory() as empty:
    skipped = os.path.join(empty, "skipped")
    os.mkdir(skipped)
    with open(os.path.join(skipped, "json.py"), "w", encoding="utf-8") as f:
        f.write("raise SystemExit('never imported: the cache says the entry has no finder')\n")
    sys.path_importer_cache[skipped] = None
    sys.path.insert(0, here)
    sys.path.insert(0, empty)
    sys.path.insert(0, os.path.join(empty, "absent"))
    sys.path.insert(0, skipped)
    sys.path.insert(1, 42)  # type: ignore[arg-type]
    sys.path.append(empty)
    found = importlib.import_module("json")
    print(found.__name__, found.dumps([1, "a"]))
    try:
        importlib.import_module("no_module_on_any_entry")
    except ModuleNotFoundError as error:
        print(type(error).__name__, error.name)
    del sys.path_importer_cache[skipped]
    sys.path[:] = start
print(sys.path == start, sys.path[0] == here)
