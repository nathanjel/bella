# clause: C-7-02
# spec: section 7
# status: P1
# source: review 2026-11-01 astra-low-03 (review log RL-60): traceback with its extension-module search replaced
"""traceback formats a ModuleNotFoundError for a module outside the closed world. On this path
CPython looks for an extension module built for another Python version
(_find_incompatible_extension_module), which phase 1 replaces with a search that finds none;
the formatting must still succeed. Nothing prints the message wording (D-08) or the frames,
which pass through importlib's internals."""
import importlib
import traceback

name = "_".join(["bella", "conformance", "no", "such", "module"])   # computed: a lookup at runtime
try:
    importlib.import_module(name)
except ModuleNotFoundError as exc:
    print("type:", type(exc).__name__, "| name:", exc.name == name)
    lines = traceback.format_exception_only(exc)
    print("format_exception_only:", len(lines), "line(s), type", lines[-1].split(":")[0])
    te = traceback.TracebackException.from_exception(exc)
    print("TracebackException:", te.exc_type_str, "| stack entries:", len(te.stack) > 0)
