"""A subpackage (C-8-10): relative imports of its parent's modules and of its own."""
from .. import plain as parent_plain
from .deep import Y

print("imppkg.sub: body runs;", __package__, parent_plain.X, Y)
