# clause: C-8-05
# spec: section 8
# status: P1
# source: dialect specification v0.4 sections 3 and 8 (PEP 810 lazy imports are [P1])
"""PEP 810: `lazy import` and `lazy from ... import` bind a proxy (types.LazyImportType, visible
through globals()); the module is initialised at the first use of the name, once, and the
binding is then the real object."""
import sys
import types

lazy import lazy_noisy
lazy from lazy_items import item

print("after the statements:", "lazy_noisy" in sys.modules, "lazy_items" in sys.modules)
print("proxies:", type(globals()["lazy_noisy"]) is types.LazyImportType, type(globals()["item"]) is types.LazyImportType)
print("first use:", lazy_noisy.VALUE)
print("second use:", lazy_noisy.VALUE, "| reified:", type(globals()["lazy_noisy"]).__name__)
print("call:", item())
print("item reified:", type(globals()["item"]).__name__, "lazy_items" in sys.modules)
