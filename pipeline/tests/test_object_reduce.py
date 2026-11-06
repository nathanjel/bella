"""object's __reduce_ex__, __reduce__ and __getstate__, compiled, against CPython: the messages case C-3-43 does not compare, and
what stops by name without copyreg."""
from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path

from pipeline.build import build
from pipeline.tests.test_review_2026_11_03 import same

MESSAGES = r"""
import copyreg
def show(f):
    try:
        print(repr(f()))
    except BaseException as e:
        print(type(e).__name__, e)
class Bad1:
    def __getnewargs_ex__(self):
        return 1
class Bad2:
    def __getnewargs_ex__(self):
        return (1,)
class Bad3:
    def __getnewargs_ex__(self):
        return (1, {})
class Bad4:
    def __getnewargs_ex__(self):
        return ((), 1)
class Bad5:
    def __getnewargs__(self):
        return 1
class BadSlots:
    __slotnames__ = 1
class Raises:
    def __getstate__(self):
        raise KeyError("x")
class AttrFails:
    __slots__ = ("a",)
    @property
    def b(self):
        raise KeyError("b")
    __slotnames__ = ["a", "b"]
for fn in (lambda: object().__reduce_ex__(), lambda: object().__reduce_ex__("a"), lambda: object().__reduce_ex__(1.5), lambda: object().__reduce_ex__(2**70), lambda: object().__reduce_ex__(2, 3), lambda: object().__reduce_ex__(protocol=2), lambda: object().__reduce__(1), lambda: object().__reduce__(x=1), lambda: object().__getstate__(1), lambda: object().__getstate__(x=1),
           lambda: object.__reduce_ex__(), lambda: object.__reduce_ex__(1), lambda: object.__getstate__(), lambda: object.__reduce__(), lambda: object().__reduce__()[1], lambda: object.__reduce_ex__, lambda: object.__getstate__, lambda: object.__reduce__, lambda: type(object.__reduce_ex__).__name__, lambda: type(object().__reduce_ex__).__name__,
           lambda: Bad1().__reduce_ex__(2), lambda: Bad2().__reduce_ex__(2), lambda: Bad3().__reduce_ex__(2), lambda: Bad4().__reduce_ex__(2), lambda: Bad5().__reduce_ex__(2), lambda: BadSlots().__reduce_ex__(2), lambda: BadSlots().__getstate__(), lambda: Raises().__reduce_ex__(2), lambda: Raises().__getstate__(), lambda: AttrFails().__getstate__(),
           lambda: (lambda: 0).__reduce_ex__(2), lambda: copyreg.__reduce_ex__(2), lambda: (i for i in ()).__reduce_ex__(2), lambda: property().__reduce_ex__(2), lambda: staticmethod(max).__reduce_ex__(2), lambda: classmethod(max).__reduce_ex__(2), lambda: int.__reduce_ex__(2), lambda: int.__getstate__(), lambda: int.__reduce__(), lambda: type("M", (type,), {})("X", (), {}).__reduce_ex__(2),
           lambda: copyreg.pickle(int, 1), lambda: copyreg.constructor(1), lambda: copyreg.__newobj__(), lambda: copyreg.__newobj__(1)):
    show(fn)
"""


def test_messages() -> None:
    same(MESSAGES)


def test_what_is_absent_stops_by_name() -> None:
    for body, name in (("object().__reduce_ex__(2)", "copyreg"), ("class C:\n    __slots__ = ('a',)\nC().__getstate__()", "copyreg")):
        with tempfile.TemporaryDirectory() as tmp:
            prog = Path(tmp, "prog.py")
            prog.write_text(f"print('start')\n{body}\n", encoding="utf-8")
            got = subprocess.run([str(build(prog, "prog.py"))], capture_output=True, text=True, check=False)
        assert (got.returncode, got.stdout) == (70, "start\n") and "not implemented" in got.stderr and name in got.stderr, (body, got)


if __name__ == "__main__":
    test_messages()
    test_what_is_absent_stops_by_name()
