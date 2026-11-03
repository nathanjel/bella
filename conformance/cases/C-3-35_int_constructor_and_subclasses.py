# clause: C-3-35
# spec: section 3 (the data model), section 6 (int), section 9 (lifetimes)
# status: P1
# source: decision 2026-11-03 (a subclass of a built-in type is that type's object); enum's IntFlag
"""int() takes an int (a subclass's value as an exact int), a bool, an object's __int__ or
__index__, or a str: ASCII whitespace around it, a sign, a base prefix with base 0 or its own
base, single underscores between digits; anything else is a ValueError, or a TypeError for an
argument that is neither, a base with a non-string, a base without one. An instance of an int
subclass is an int: arithmetic on it gives plain ints, it compares and hashes as its value, it
indexes, and it has attributes of its own; the subclass's overrides are reached where CPython's
slots would reach them. A nonempty __slots__ is refused."""


class Indexed:
    def __index__(self) -> int:
        return 7


class Converted:
    def __int__(self) -> int:
        return 9


class Wrong:
    def __int__(self) -> object:
        return "nine"


def kind(make: object) -> str:
    try:
        made = make()  # type: ignore[operator]  # a thunk, called on purpose
    except (TypeError, ValueError) as exc:
        return type(exc).__name__
    return repr(made) + " " + type(made).__name__


for label, thunk in (("int()", lambda: int()), ("int(5)", lambda: int(5)), ("int(True)", lambda: int(True)),  # noqa: UP018 -- the constructor is the point
                     ("spaces and sign", lambda: int(" \t+7\n")), ("minus zero", lambda: int("-0")),
                     ("underscores", lambda: int("1_000")), ("hex, base 16", lambda: int("0x1F", 16)),
                     ("hex, base 0", lambda: int("0x_1f", 0)), ("binary, base 0", lambda: int("0b101", 0)),
                     ("octal, base 0", lambda: int("0o17", 0)), ("base 36", lambda: int("z", 36)),
                     ("base 2", lambda: int("-1010", 2)), ("zeros, base 0", lambda: int("00", 0)),
                     ("leading zero, base 0", lambda: int("012", 0)), ("double underscore", lambda: int("1__0")),
                     ("leading underscore", lambda: int("_1")), ("trailing underscore", lambda: int("1_")),
                     ("empty", lambda: int("")), ("blank", lambda: int(" ")), ("trailing letter", lambda: int("12a")),
                     ("digit beyond the base", lambda: int("8", 8)), ("base 1", lambda: int("5", 1)),
                     ("base 37", lambda: int("5", 37)), ("an int with a base", lambda: int(5, 10)),  # type: ignore[call-overload]  # wrong types on purpose
                     ("a base alone", lambda: int(base=10)), ("a list", lambda: int([])),  # type: ignore[call-overload]  # wrong types on purpose
                     ("__index__", lambda: int(Indexed())), ("__int__", lambda: int(Converted())),
                     ("__int__ not an int", lambda: int(Wrong()))):  # type: ignore[call-overload]  # as above
    print(label + ":", kind(thunk))


class Plain(int):
    pass


class Doubled(int):
    def __new__(cls, value: int) -> Doubled:
        return int.__new__(cls, value * 2)

    def __add__(self, other: int) -> int:
        return int(self) * 100 + other

    def __repr__(self) -> str:
        return "Doubled(" + str(int(self)) + ")"


p = Plain(5)
print(p, repr(p), type(p).__name__, isinstance(p, int), type(p + 1).__name__, p + 1, p * Plain(3), -p, type(-p).__name__)
print(p == 5, hash(p) == hash(5), {5: "five"}[p], [10, 20, 30, 40, 50, 60][p], bool(Plain(0)), type(int(p)).__name__)
print(Plain("12", 8), Plain(), list(range(Plain(3))), f"{p}", str(p))
d = Doubled(4)
print(d, repr(d), d + 1, 1 + d, type(d).__name__, int(d))
p.label = "attribute"  # type: ignore[attr-defined]  # an attribute of the instance's own
print(p.label, vars(p))  # type: ignore[attr-defined]  # as above


class Probe:
    def __init__(self, name: str) -> None:
        self.name = name

    def __del__(self) -> None:
        print("dies", self.name)


q = Plain(1)
q.a = Probe("a")  # type: ignore[attr-defined]  # an attribute of the instance's own
q.b = Probe("b")  # type: ignore[attr-defined]  # as above
del q
try:
    class Slotted(int):
        __slots__ = ("x",)
    print("made")
except TypeError:
    print("nonempty __slots__: TypeError")
print("end")
