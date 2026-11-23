"""A module the program keeps from sys (C-9-13): it outlives the first collection, and its names are cleared in two
passes, those with one underscore first."""
from exitpkg import fin

LABEL = "kept"
_under = fin.C("kept._under", globals())
plain = fin.C("kept.plain", globals())
