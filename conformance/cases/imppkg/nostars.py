"""Without __all__, import * binds the public names of the module's namespace (C-8-10)."""
from imppkg import plain as _plain

a = 1
_b = 2
version = _plain.X + 2
