# clause: C-3-08
# spec: section 3 (richcompare returns an object; truth is taken only where needed)
# status: P1
# source: review round 2, finding 5 (__eq__ may return any object or NotImplemented)
"""a == b returns whatever __eq__ returns; `if` applies truth; NotImplemented falls back to identity."""
from typing import Any


class Odd:
    def __eq__(self, other: Any) -> Any:
        return "comparison-result"


class Silent:
    def __eq__(self, other: Any) -> Any:
        return NotImplemented


a, b = Odd(), Odd()
r = a == b
print("== returns:", r, type(r).__name__)
print("truth in if:", "yes" if a == b else "no")
s1, s2 = Silent(), Silent()
print("NotImplemented both ways falls back to identity:", s1 == s2, s1 == s1)
print("!= derives from __eq__ by inverting truth:", s1 != s2)
