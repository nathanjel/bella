# clause: C-8-09
# spec: section 8
# status: P1
# source: Gate 0 task 5, the staging prototype (docs/staging.md): staging adds nothing observable
"""collections.namedtuple and typing.NamedTuple build __new__ with eval while the class is
defined (spec section 8). The classes behave as CPython's: field order and defaults, renamed
fields, the module a namedtuple reports, a subclass with __slots__ = () and a property (as
urllib.parse does), two classes with the same fields, a namedtuple a function makes each time
it is called with literal fields, docstrings, copying, pattern matching, and the errors raised
while a definition is checked, before any code is generated."""
import collections
import copy
import typing

Point = collections.namedtuple("Point", "x y", defaults=[0])
print("Point:", Point._fields, Point._field_defaults, Point.__module__, Point.__doc__)
Renamed = collections.namedtuple("Renamed", ["abc", "def", "abc", "_x"], rename=True)
print("Renamed:", Renamed._fields)
Placed = collections.namedtuple("Placed", "lat lon", module="geo")
print("Placed:", Placed.__module__, Placed.__qualname__)
Same = collections.namedtuple("Same", "x y")
print("Same:", Same._fields == Point._fields, len({Same, Point}))


class Url(collections.namedtuple("UrlBase", "scheme host")):
    __slots__ = ()

    @property
    def origin(self) -> str:
        return f"{self.scheme}://{self.host}"


class Version(typing.NamedTuple):
    major: int
    minor: int = 0
    print("class body of Version")  # type: ignore[misc]  # mypy allows only fields here; Python runs it

    def bump(self) -> "Version":  # noqa: UP037  # the class is not bound yet
        return self._replace(minor=self.minor + 1)


def make_local() -> type:
    Local = collections.namedtuple("Local", "p q")
    return Local


p = Point(1)
print(p, p.x, p._asdict(), p._replace(y=5), Point._make([7, 8]), p == (1, 0))
print(Point.__match_args__, Point.__new__.__defaults__, Point.__new__.__doc__, Point.x.__doc__)
print(copy.copy(p) == p, copy.deepcopy(p) == p, type(copy.copy(p)).__name__)
u = Url("https", "example.org")
print(u, u.origin, hasattr(u, "__dict__"), Url._fields)
v = Version(1)
print(v, v.bump(), Version._field_defaults, sorted(Version.__annotations__))
Local = make_local()
print(Local(1, 2), make_local() is Local, make_local()._fields)  # type: ignore[attr-defined]
match Point(2, 3):
    case Point(x, y):
        print("matched", x, y)
for fields in ("x x", "_x", "x def"):
    try:
        collections.namedtuple("Bad", fields)
    except ValueError as exc:
        print("rejected", repr(fields), exc)
