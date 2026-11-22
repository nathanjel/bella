"""How a Struct gets its format in 3.15 (reviews A23 and A34: RL-549, RL-776; conformance case C-7-92).

`Struct.__new__` takes the format; `Struct.__init__` takes it too, for a class with an `__init__` of its own, and each
warns where the other was meant: a DeprecationWarning from `__new__` for a format that is missing, one too many or
invalid when the class has its own `__init__`, a FutureWarning from `__init__` for another format than the object has. A
Struct with no format has no `format`, a size of -1, and methods that raise RuntimeError once their arguments are
converted. The prelude had one way (the format to `__new__`), stopped by name for a class over Struct and for a second
format, and returned None for an `__init__` without one.

59 rows in one program on each side: the state of the object after each way of making and initialising it, and the
warnings by category and text. The case holds the same without the texts.

Run under pytest or directly: python3 -m pipeline.tests.test_struct_new_and_init
"""
from __future__ import annotations

from pipeline.tests.test_review_2026_11_19 import same

ROWS = r'''
import struct, warnings, sys
S = struct.Struct
def outcome(f):
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        try: r = f()
        except BaseException as e: r = type(e).__name__
        return r, [(type(x.message).__name__, str(x.message)) for x in w]
def state(s):
    out = []
    for name in ("format", "size"):
        try: out.append(getattr(s, name))
        except BaseException as e: out.append(type(e).__name__)
    for call in (lambda: s.pack(1), lambda: repr(s), lambda: s.unpack(b"\x01")):
        try: out.append(call())
        except BaseException as e: out.append(type(e).__name__)
    return out
class Plain(S): pass
class WithInit(S):
    def __init__(self, *a, **k): pass
class InitCalls(S):
    def __init__(self, fmt="b"): super().__init__(fmt)
class WithNew(S):
    def __new__(cls, *a, **k): return super().__new__(cls, *a, **k)
class NewFixed(S):
    def __new__(cls, *a, **k): return super().__new__(cls, "b")
rows = {
 "S.__new__(S)": lambda: state(S.__new__(S)),
 "S()": lambda: S(),
 "S('b')": lambda: state(S("b")),
 "S(format='b')": lambda: state(S(format="b")),
 "S(b'b')": lambda: state(S(b"b")),
 "S('b', 1)": lambda: S("b", 1),
 "S(fmt='b')": lambda: S(fmt="b"),
 "S('zz')": lambda: S("zz"),
 "S(1)": lambda: S(1),
 "S('b').__init__('b')": lambda: state((lambda s: (s.__init__("b"), s)[1])(S("b"))),
 "S('b').__init__('h')": lambda: state((lambda s: (s.__init__("h"), s)[1])(S("b"))),
 "S('b').__init__('h') twice": lambda: state((lambda s: (s.__init__("h"), s.__init__("b"), s)[2])(S("b"))),
 "S('b').__init__()": lambda: S("b").__init__(),
 "S('b').__init__('zz')": lambda: (lambda s: (outcome(lambda: s.__init__("zz")), state(s)))(S("b")),
 "S.__new__(S).__init__('b')": lambda: state((lambda s: (s.__init__("b"), s)[1])(S.__new__(S))),
 "Plain('b')": lambda: state(Plain("b")),
 "Plain()": lambda: Plain(),
 "WithInit('b')": lambda: state(WithInit("b")),
 "WithInit()": lambda: state(WithInit()),
 "WithInit('b', 1)": lambda: state(WithInit("b", 1)),
 "WithInit('zz')": lambda: state(WithInit("zz")),
 "WithInit(1)": lambda: state(WithInit(1)),
 "InitCalls()": lambda: state(InitCalls()),
 "InitCalls('h')": lambda: state(InitCalls("h")),
 "WithNew('b')": lambda: state(WithNew("b")),
 "WithNew()": lambda: WithNew(),
 "WithNew('b', 1)": lambda: WithNew("b", 1),
 "NewFixed('h')": lambda: state(NewFixed("h")),
 "NewFixed()": lambda: state(NewFixed()),
 "type(Plain('b')).__name__": lambda: (type(Plain("b")).__name__, repr(Plain("b")), Plain("b").__dict__ if hasattr(Plain("b"), "__dict__") else "no dict"),
}
class Shadow(S):
    size = 99
    format = "zz"
    _codes = None
    _length = 7
def strict(f):
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        try: return f()
        except BaseException as e: return type(e).__name__
def bare(): return S.__new__(S)
rows.update({
 "S.__new__(S, 'b', 1)": lambda: state(S.__new__(S, "b", 1)),
 "S.__new__(S, x=1)": lambda: state(S.__new__(S, x=1)),
 "S.__new__(Plain, 'b')": lambda: state(S.__new__(Plain, "b")),
 "S.__new__(WithInit)": lambda: state(S.__new__(WithInit)),
 "S.__new__(int)": lambda: S.__new__(int),
 "WithNew(format='b')": lambda: state(WithNew(format="b")),
 "S('b').__init__(b'b')": lambda: state((lambda s: (s.__init__(b"b"), s)[1])(S("b"))),
 "S('b').__init__(format='b')": lambda: state((lambda s: (s.__init__(format="b"), s)[1])(S("b"))),
 "S('b').__init__('b', 1)": lambda: S("b").__init__("b", 1),
 "S('b').__init__(1)": lambda: (lambda s: (outcome(lambda: s.__init__(1)), state(s)))(S("b")),
 "Plain('b').__init__('h')": lambda: state((lambda s: (s.__init__("h"), s)[1])(Plain("b"))),
 "WithInit('b').__init__('h')": lambda: state((lambda s: (S.__init__(s, "h"), s)[1])(WithInit("b"))),
 "WithInit('b'); S.__init__ same": lambda: state((lambda s: (S.__init__(s, "b"), S.__init__(s, "b"), s)[2])(WithInit("b"))),
 "bare unpack(5)": lambda: bare().unpack(5),
 "bare unpack(b'x')": lambda: bare().unpack(b"x"),
 "bare unpack_from(b'x', 'a')": lambda: bare().unpack_from(b"x", "a"),
 "bare unpack_from(b'x')": lambda: bare().unpack_from(b"x"),
 "bare pack_into(bytearray, 0, 1)": lambda: bare().pack_into(bytearray(1), 0, 1),
 "bare pack_into(5, 0)": lambda: bare().pack_into(5, 0),
 "bare iter_unpack(5)": lambda: bare().iter_unpack(5),
 "bare pack()": lambda: bare().pack(),
 "bare __sizeof__()": lambda: bare().__sizeof__(),
 "Shadow('b')": lambda: (lambda s: (s.pack(1), s.unpack(b"\x01"), s.size, s.format, repr(s), S.size.__get__(s), S.format.__get__(s)))(Shadow("b")),
 "strict WithInit()": lambda: strict(lambda: state(WithInit())),
 "strict WithInit('zz')": lambda: strict(lambda: state(WithInit("zz"))),
 "strict WithInit('b', 1)": lambda: strict(lambda: state(WithInit("b", 1))),
 "strict S('b').__init__('h')": lambda: (lambda s: (strict(lambda: s.__init__("h")), state(s)))(S("b")),
 "strict Plain('b')": lambda: strict(lambda: state(Plain("b"))),
 "module functions": lambda: (struct.pack("b", 1), struct.unpack("b", b"\x01"), struct.calcsize("h"), type(struct.Struct("b")).__name__),
})
for label, f in rows.items():
    print(label, "->", outcome(f))
'''


def test_every_way_of_making_and_initialising_a_struct() -> None:
    same(ROWS)


if __name__ == "__main__":
    test_every_way_of_making_and_initialising_a_struct()
    print("ok")
