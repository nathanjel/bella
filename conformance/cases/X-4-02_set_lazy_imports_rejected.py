# clause: X-4-02
# spec: section 4
# status: X
# expect: E-04
# source: dialect specification v0.4 section 4 (sys.set_lazy_imports is import-system customisation)
"""The compiler must reject this file with E-04 at the call; CPython runs it."""
import sys

sys.set_lazy_imports("all")
print(sys.get_lazy_imports())
