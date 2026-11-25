"""A module whose body raises, with nothing in a cycle: what holds its namespace is its frame, in the traceback."""
import sys

from dyingpkg.watch import Marker, watched

held = Marker("fails.held")
watched(sys.modules[__name__], "fails")
raise ValueError("fails")
