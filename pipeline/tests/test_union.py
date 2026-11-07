"""typing.Union, compiled, against CPython: the messages, which case C-3-39 does not compare, and what stops by name."""
from __future__ import annotations

import subprocess
import tempfile
import textwrap
from pathlib import Path
from typing import Any

from pipeline.build import build
from pipeline.tests.test_review_2026_11_03 import same

MESSAGES = r"""
import types
def show(f):
    try:
        print(repr(f()))
    except BaseException as e:
        print(type(e).__name__, e)
class C:
    pass
class Eq:
    def __init__(self, n):
        self.n = n
    def __eq__(self, other):
        return isinstance(other, Eq) and self.n == other.n
    def __repr__(self):
        return "Eq(" + str(self.n) + ")"
class Raises:
    def __hash__(self):
        raise ValueError("inside hash")
    def __repr__(self):
        return "Raises()"
def f(*args):
    return args
u = int | str
g = list[Eq(1)]
for fn in (lambda: int | 1, lambda: 1 | int, lambda: int | "a", lambda: "a" | int, lambda: int | 1.5, lambda: int | [], lambda: [] | int, lambda: int | (int,), lambda: int | {}, lambda: {} | int, lambda: int | {1}, lambda: {1} | int, lambda: None | None, lambda: list[int] | 1, lambda: 1 | list[int], lambda: list[int] | "a", lambda: "a" | list[int], lambda: int & str, lambda: int ^ str, lambda: int + str, lambda: ~int, lambda: -int, lambda: C() | int, lambda: int | C(),
           lambda: type.__or__(1, int), lambda: type.__or__(int), lambda: type.__or__(int, str, float), lambda: type.__or__(), lambda: type.__ror__(1, int), lambda: type.__or__(int, x=1), lambda: list[int].__or__(), lambda: list[int].__ror__(),
           lambda: types.UnionType(), lambda: types.UnionType(int, str), lambda: type(u)(int), lambda: object.__new__(types.UnionType), lambda: type("X", (types.UnionType,), {}), lambda: u(), lambda: u(1), lambda: setattr(u, "__args__", ()), lambda: delattr(u, "__args__"), lambda: setattr(u, "x", 1), lambda: delattr(u, "x"), lambda: u.nothing, lambda: setattr(u, "__name__", "x"), lambda: setattr(u, "__origin__", "x"), lambda: setattr(u, "__parameters__", ()), lambda: setattr(u, "__qualname__", "x"), lambda: setattr(u, "__module__", "x"), lambda: delattr(u, "__name__"), lambda: delattr(u, "__module__"),
           lambda: list(u), lambda: iter(u), lambda: len(u), lambda: u[int], lambda: u[()], lambda: u[0], lambda: 1 in u, lambda: f(*u), lambda: [*u], lambda: {**u}, lambda: u < u, lambda: u >= 1, lambda: u + 1, lambda: -u, lambda: u.__or__(), lambda: u.__or__(1, 2), lambda: u.__ror__(), lambda: u.__or__(x=1), lambda: u.__repr__(1), lambda: u.__hash__(1), lambda: u.__eq__(), lambda: u.__ne__(1, 2), lambda: u.__lt__(), lambda: u.__getitem__(), lambda: u.__getitem__(1, 2),
           lambda: u.__mro_entries__((u,)), lambda: u.__mro_entries__(), lambda: u.__mro_entries__(1, 2), lambda: u.__mro_entries__(x=1), lambda: types.UnionType.__class_getitem__(), lambda: types.UnionType.__class_getitem__(1, 2), lambda: types.UnionType.__class_getitem__(x=1), lambda: types.UnionType[()], lambda: types.UnionType.__class_getitem__(()),
           lambda: types.UnionType.__or__(1, 2), lambda: types.UnionType.__or__(), lambda: types.UnionType.__ror__(1, 2), lambda: types.UnionType.__repr__(1), lambda: types.UnionType.__repr__(), lambda: types.UnionType.__hash__(1), lambda: types.UnionType.__eq__(1, 2), lambda: types.UnionType.__ne__(1, 2), lambda: types.UnionType.__lt__(1, 2), lambda: types.UnionType.__getitem__(1, 2), lambda: types.UnionType.__dict__["__args__"].__get__(1), lambda: types.UnionType.__dict__["__name__"].__get__(1), lambda: types.UnionType.__dict__["__parameters__"].__get__(1), lambda: types.UnionType.__dict__["__origin__"].__set__(u, 1),
           lambda: isinstance(1, list[int] | str), lambda: issubclass(int, list[int] | str), lambda: isinstance(1, int | list[str]), lambda: isinstance("a", int | list[str]), lambda: issubclass(int, int | list[str]), lambda: issubclass(1, int | str), lambda: issubclass(str, int | list[str]),
           lambda: hash(g | int), lambda: {g | int}, lambda: {g | int: 1}, lambda: (g | int) == (int | list[Eq(1)]), lambda: (g | list[Eq(2)]).__args__, lambda: (Raises | int), lambda: hash(list[Raises()] | int), lambda: list[Raises()] | int,
           lambda: repr(int | None), lambda: repr(None | int), lambda: repr(C | int), lambda: repr(list[int] | None), lambda: repr(dict[str, list[int]] | None), lambda: str(int | str | None), lambda: format(int | str), lambda: format(int | str, ""), lambda: format(int | str, "x"), lambda: "%s" % (int | str), lambda: f"{int | str}", lambda: (int | str).__str__(), lambda: (int | str).__format__(""), lambda: (int | str).__reduce__() if False else 0, lambda: (int | str).__sizeof__() if False else 0,
           lambda: types.UnionType, lambda: repr(types.UnionType), lambda: type(types.UnionType), lambda: types.UnionType.__base__, lambda: types.UnionType.__mro__, lambda: types.UnionType.__name__, lambda: types.UnionType.__qualname__, lambda: types.UnionType.__module__, lambda: setattr(types.UnionType, "x", 1), lambda: setattr(types.UnionType, "__name__", "x"), lambda: delattr(types.UnionType, "__or__"), lambda: types.UnionType.__args__, lambda: types.UnionType.__origin__, lambda: types.UnionType.__parameters__, lambda: types.UnionType.__doc__, lambda: u.__doc__, lambda: u.__class__, lambda: u.__args__, lambda: u.__name__, lambda: u.__qualname__, lambda: u.__module__, lambda: u.__origin__, lambda: u.__parameters__, lambda: sorted(dir(u))):
    show(fn)
"""

REFUSED = (
    ("(int | str) | 1", "importing '"),
    ("1 | (int | str)", "importing '"),
    ("import types\ntypes.UnionType[int, 'a']", "compile()"),      # typing compiles the forward reference eagerly (_make_forward_ref)
)


def pytest_generate_tests(metafunc: Any) -> None:
    if "refused" in metafunc.fixturenames:
        metafunc.parametrize("refused", REFUSED, ids=[text for text, _ in REFUSED])


def test_messages() -> None:
    same(MESSAGES)


def test_what_is_not_there_yet_stops_by_name(refused: tuple[str, str]) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        prog = Path(tmp, "prog.py")
        prog.write_text(textwrap.dedent(refused[0]) + "\n", encoding="utf-8")
        got = subprocess.run([str(build(prog, "prog.py"))], capture_output=True, text=True, check=False, timeout=60)
    assert got.returncode == 70 and "not implemented" in got.stderr and refused[1] in got.stderr, got


if __name__ == "__main__":
    test_messages()
