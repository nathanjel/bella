"""Fixture for C-8-06: its initialisation fails."""
print("  [lazy_broken initialising]")
raise LookupError("lazy_broken refuses to initialise")
