# clause: C-8-04
# spec: section 8
# status: P1
# source: review round 1, finding 7 (modules initialise at the first import statement that reaches them)
"""A module body runs when the import statement executes, not earlier; later imports do not rerun it."""
import sys

print("before first import")
import cycpkg  # noqa: E402  -- the package __init__ runs now, after the line above

print("after first import; in sys.modules:", "cycpkg" in sys.modules)


def late() -> None:
    import cycpkg  # noqa: F401  -- already initialised: nothing runs
    print("function-local import done")


late()
if False:
    import this_module_does_not_exist  # noqa: F401  -- never reached, never resolved
print("conditional import skipped")
