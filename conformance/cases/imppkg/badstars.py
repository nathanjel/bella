"""An __all__ with an item that is not a str (C-8-10)."""
__all__ = ["a", 5]  # type: ignore[list-item]  # a wrong item on purpose
a = 1
