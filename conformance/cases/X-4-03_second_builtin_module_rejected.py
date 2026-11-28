# clause: X-4-03
# spec: section 4
# status: X
# expect: E-04
# source: dialect specification v0.50 section 4 (a second module object of a built-in module is import-system customisation)
"""The program must stop by name with E-04 at the second import, which only the run meets; CPython makes a second module
object of math there."""
import importlib
import math
import sys

del sys.modules["math"]
again = importlib.import_module("math")
print(again is math)
