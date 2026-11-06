"""What the methods of a type written in C say when they are misused, compiled, against CPython: the messages case C-3-42 does not
compare. A type the runtime writes in Python and one it writes in C++ answer alike."""
from __future__ import annotations

from pipeline.tests.test_review_2026_11_03 import same

MESSAGES = r"""
import collections
import functools
import itertools
import os
import weakref
def show(f):
    try:
        print(repr(f()))
    except BaseException as e:
        print(type(e).__name__, e)
count = itertools.count
for_chain = itertools.chain.__dict__["from_iterable"]
class Sub(count):
    pass
class Fresh(count):
    def __new__(cls):
        return object.__new__(cls)
for fn in (lambda: object.__new__(count), lambda: object.__new__(functools.partial), lambda: object.__new__(collections.deque), lambda: object.__new__(Sub), lambda: Fresh(), lambda: tuple.__new__(os.terminal_size, (1, 2)), lambda: object.__new__(property), lambda: object.__new__(staticmethod), lambda: object.__new__(classmethod),
           lambda: count.__new__(), lambda: count.__new__(1), lambda: count.__new__(int), lambda: count.__new__(tuple), lambda: collections.deque.__new__(1), lambda: property.__new__(int), lambda: property.__new__(), lambda: staticmethod.__new__(1), lambda: map.__new__(int), lambda: os.terminal_size.__new__(int, (1, 2)),
           lambda: count.__next__(), lambda: count.__next__(1), lambda: count.__next__(count(), 1), lambda: count.__next__(count(), x=1), lambda: count(0).__next__(1), lambda: count(0).__next__(x=1), lambda: count.__iter__(), lambda: count.__repr__(1), lambda: collections.deque.__len__(collections.deque(), 1), lambda: collections.deque.__getitem__(collections.deque()), lambda: collections.deque.__setitem__(collections.deque(), 0), lambda: functools.partial.__call__(), lambda: functools.partial.__call__(1), lambda: functools.partial(max).__call__(), lambda: functools.partial.__repr__(1), lambda: functools.partial.__repr__(functools.partial(max), 1),
           lambda: collections.deque.append(), lambda: collections.deque.append(1), lambda: collections.deque.append(1, 2), lambda: collections.deque().append(), lambda: collections.deque().append(1, 2), lambda: collections.deque.popleft(collections.deque(), 1), lambda: collections.deque().popleft(), lambda: count.__reduce__ if False else None, lambda: functools.partial.__reduce__(), lambda: functools.partial.__reduce__(1),
           lambda: for_chain(), lambda: for_chain(1), lambda: for_chain(int), lambda: for_chain(int, []), lambda: for_chain.__get__(None, int), lambda: for_chain.__get__(1), lambda: for_chain.__get__(None, 1), lambda: for_chain.__get__(None, None), lambda: for_chain.__get__(), lambda: dict.__dict__["fromkeys"](), lambda: dict.__dict__["fromkeys"](1), lambda: dict.__dict__["fromkeys"](int), lambda: int.__dict__["from_bytes"](str),
           lambda: int.__add__(), lambda: int.__add__(1), lambda: int.__add__("a", 1), lambda: int.__add__(1, 2, 3), lambda: (1).__add__(), lambda: (1).__add__(1, 2), lambda: int.__add__.__get__(), lambda: int.__add__.__get__(None, None), lambda: int.__add__.__get__("a"), lambda: int.__add__.__get__(None, int) is int.__add__, lambda: str.join(), lambda: str.join(1), lambda: str.join.__get__(1), lambda: object.__init__.__get__(1).__self__, lambda: object.__repr__, lambda: object.__init__, lambda: object.__dir__, lambda: repr(object().__repr__).split(" at ")[0], lambda: repr(int.__add__), lambda: repr(str.join), lambda: repr(dict.__dict__["fromkeys"]),
           lambda: setattr(int.__add__, "__name__", "x"), lambda: setattr((1).__add__, "__name__", "x"), lambda: setattr(int.__add__, "x", 1), lambda: setattr((1).__add__, "x", 1), lambda: delattr(int.__add__, "__name__"), lambda: (1).__add__ < (1).__add__, lambda: int.__add__.nothing, lambda: (1).__add__.nothing, lambda: count.__next__.nothing, lambda: count(0).__next__.nothing, lambda: type("X", (type(int.__add__),), {}), lambda: type("X", (type((1).__add__),), {}), lambda: type(int.__add__)(), lambda: type((1).__add__)(),
           lambda: weakref.ProxyType(), lambda: weakref.CallableProxyType(max), lambda: object.__new__(weakref.ProxyType), lambda: weakref.ProxyType.__new__(weakref.ProxyType)):
    show(fn)
"""


def test_messages() -> None:
    same(MESSAGES)


if __name__ == "__main__":
    test_messages()
