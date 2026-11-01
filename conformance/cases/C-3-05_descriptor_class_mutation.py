# clause: C-3-05
# spec: section 3
# status: P1
# source: review round 3, finding 3 (adding __set__ to a descriptor's class changes lookup precedence
#         without any change to the class that holds the descriptor)
"""A non-data descriptor shadowed by an instance attribute becomes a data descriptor and wins."""
from typing import Any


class Desc:
    def __get__(self, obj: Any, owner: Any = None) -> int:
        return 1


class Holder:
    attr = Desc()


h = Holder()
h.__dict__["attr"] = 99
print("instance wins over non-data descriptor:", h.attr)


def set_(self: Desc, obj: Any, value: Any) -> None:
    pass


Desc.__set__ = set_          # Desc is now a data descriptor; Holder itself did not change
print("data descriptor wins after promotion:", h.attr)
del Desc.__set__
print("instance visible again after demotion:", h.attr)
