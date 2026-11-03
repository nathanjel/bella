"""A submodule whose body raises (C-8-10): it leaves sys.modules, and a later import runs it again."""
import sys

print("imppkg.failing: body runs; in sys.modules while it runs:", __name__ in sys.modules)
PARTIAL = 1
raise LookupError("failing on purpose")
