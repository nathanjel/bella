# clause: X-4-04
# spec: section 4
# status: X
# expect: E-04
# source: dialect specification v0.50 section 4 (sys.meta_path is import-system customisation; Question 55)
"""The program must stop by name with E-04 at the import after the write, which only the run meets; CPython asks the
program's finder there."""
import importlib
import sys


class Finder:
    def find_spec(self, name: str, path: object = None, target: object = None) -> None:
        print("finder asked", name)


sys.meta_path.insert(0, Finder())
print(importlib.import_module("json").__name__)
