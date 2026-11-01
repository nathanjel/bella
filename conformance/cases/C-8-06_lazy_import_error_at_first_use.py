# clause: C-8-06
# spec: section 8
# status: P1
# source: dialect specification v0.4 section 3 (PEP 810: import errors are raised at first use)
"""PEP 810: a lazily imported module that fails to initialise raises at the first use of the
name, not at the statement; the failed module is not left in sys.modules."""
import sys

lazy import lazy_broken

print("statement done:", "lazy_broken" in sys.modules)
for attempt in (1, 2):
    try:
        lazy_broken.anything  # type: ignore[attr-defined]  # noqa: B018  # the use that initialises the module
    except LookupError as exc:
        print("attempt", attempt, type(exc).__name__, exc.args, "| in sys.modules:", "lazy_broken" in sys.modules)
