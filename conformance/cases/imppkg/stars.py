"""from imppkg.stars import * binds __all__'s names, a private one included (C-8-10)."""
__all__ = ["a", "_b"]
a = 1
_b = 2
c = 3
