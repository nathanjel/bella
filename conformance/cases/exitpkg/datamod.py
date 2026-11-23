"""A module with no function (C-9-13): its namespace goes with the module, as soon as sys.modules lets go of it."""
from exitpkg import fin

obj = fin.C("data", {"LABEL": "a copy"})
