# clause: C-8-25
# spec: section 8
# status: P1
# source: the author's decision of 2026-11-28 (Question 64): the lazy-imports mode a program reads (D-18)
"""The lazy-imports mode a program can read: sys.get_lazy_imports() is "normal", the mode D-18 fixes, before a lazy import
is used and after, and sys.get_lazy_imports_filter() is None, since no filter can be set (E-04); both are built-in
functions that take no argument."""
import sys

lazy import json

print(sys.get_lazy_imports(), type(sys.get_lazy_imports()).__name__, sys.get_lazy_imports_filter())
print(json.dumps([1]), sys.get_lazy_imports(), sys.get_lazy_imports_filter())
for read in (sys.get_lazy_imports, sys.get_lazy_imports_filter):
    try:
        read(1)  # type: ignore[call-arg]
    except TypeError as error:
        print(read.__name__, type(read).__name__, type(error).__name__)
