# clause: C-8-07
# spec: section 8
# status: P1
# source: dialect specification v0.4 section 3 (PEP 810 __lazy_modules__); review log RL-55
"""PEP 810's compatibility form: a plain module-level import of a module named in
__lazy_modules__ at that point is lazy. The list is read per imported module and at each
statement, and not inside try (measured on CPython 3.15.2, review log RL-55)."""
import sys

__lazy_modules__ = ["lazy_noisy"]
import lazy_items, lazy_noisy  # noqa: E401, I001  # one statement, two modules, one of them lazy

print("lazy_noisy deferred:", "lazy_noisy" not in sys.modules, "| lazy_items loaded:", "lazy_items" in sys.modules)
print("use:", lazy_noisy.VALUE, lazy_items.item())
