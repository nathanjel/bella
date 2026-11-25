"""A module whose body raises after it defined a class: the class's method holds the namespace, which holds the class."""
import sys

from dyingpkg.watch import Marker, watched

held = Marker("fails_class.held")


class K:
    def method(self) -> Marker:
        return held


watched(sys.modules[__name__], "fails_class")
raise ValueError("fails_class")
