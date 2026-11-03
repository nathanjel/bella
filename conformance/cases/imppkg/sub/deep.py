"""Two levels down (C-8-10): from ..plain import X, and an import beyond the top-level package."""
from ..plain import X

Y = X + 1
try:
    __import__("", globals(), None, ["nothing"], 3)  # from ... import nothing: beyond the top-level package on purpose
except ImportError as exc:
    print("imppkg.sub.deep: beyond the top-level package ->", type(exc).__name__)
