"""A module that puts another object into sys.modules under its own name (C-8-10): the import
statement binds that object."""
import sys


class StandIn:
    def __repr__(self) -> str:
        return "<the stand-in>"


sys.modules[__name__] = StandIn()  # type: ignore[assignment]  # not a module, on purpose
