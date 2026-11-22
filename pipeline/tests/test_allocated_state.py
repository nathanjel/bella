"""The state an allocator leaves: a type whose tp_new is object's has no __new__ of its own.

Six of the io types CPython writes in C take object's allocator: BufferedReader, BufferedWriter, BufferedRandom,
BufferedRWPair, IncrementalNewlineDecoder and TextIOWrapper have no `__new__` in their dict, `cls.__new__ is
object.__new__`, and what `object.__new__(cls)` gives is the struct as tp_alloc zeroed it, which each method answers as an
object that was never initialised. The preludes' classes had a `__new__` of their own to set that state (six of the names of
`conformance/names-surplus.txt`; review A33, RL-726, made them check their arguments as object's does). Now the class says
what the zeroed struct is in `__alloc__(self)`, which the runtime keeps beside the class and calls from object's allocator
for an instance of the type or of a class that derives from it (`allocated_state`, `runtime/src/call.cpp`).

Run under pytest or directly: python3 -m pipeline.tests.test_allocated_state
"""
from __future__ import annotations

from pipeline.tests.test_review_2026_11_19 import same

PROGRAM = r'''
import io
KINDS = (io.BufferedReader, io.BufferedWriter, io.BufferedRandom, io.BufferedRWPair, io.IncrementalNewlineDecoder, io.TextIOWrapper)
def arguments(kind):
    if kind is io.BufferedRWPair: return (io.BytesIO(), io.BytesIO())
    if kind is io.IncrementalNewlineDecoder: return (None, True)
    return (io.BytesIO(),)
def answer(call):
    try: return type(call()).__name__
    except Exception as e: return type(e).__name__
for kind in KINDS:
    print(kind.__name__, "__new__" in vars(kind), kind.__new__ is object.__new__, "__alloc__" in vars(kind), hasattr(kind, "__alloc__"))
    for made in (object.__new__(kind), kind.__new__(kind), kind.__new__(kind, 1, 2)):
        calls = [lambda: made.readable(), lambda: made.closed, lambda: made.read(), lambda: made.flush(), lambda: made.close(),
                 lambda: made.decode("a"), lambda: made.getstate(), lambda: made.reset(), lambda: made.newlines, lambda: made.detach(),
                 lambda: made.fileno(), lambda: made.name, lambda: made.mode, lambda: made.raw, lambda: made.buffer,
                 lambda: made.encoding, lambda: made.errors, lambda: made.line_buffering, lambda: made.tell(), lambda: made.seekable(),
                 lambda: made.isatty(), lambda: made.peek(), lambda: made.write(b"a"), lambda: made.write("a"), lambda: made._finalizing,
                 lambda: made.__getstate__(), lambda: iter(made), lambda: next(made), lambda: made.__enter__()]
        print("  ", [answer(call) for call in calls])
        try: print("  ", repr(made))
        except ValueError: print("   ValueError for its repr")
        made.__init__(*arguments(kind))
        print("  ", "initialised after:", answer(lambda: made.readable() if kind is not io.IncrementalNewlineDecoder else made.decode("a")))
        if kind in (io.BufferedReader, io.BufferedWriter, io.BufferedRandom):
            print("  ", "raw:", type(made.raw).__name__, type(made.detach()).__name__, made.raw, answer(lambda: made.closed))
        if kind is io.TextIOWrapper:
            made.detach()
            print("  ", "detached:", [answer(lambda: getattr(made, name)) for name in
                                     ("encoding", "line_buffering", "write_through", "errors", "closed", "buffer", "name", "newlines", "_finalizing")])
    class Tagged(kind):
        def __new__(cls, *args):
            self = super().__new__(cls)
            self.tag = len(args)
            return self
    t = Tagged(*arguments(kind))
    print("  ", type(t).__name__, t.tag, answer(lambda: t.readable() if kind is not io.IncrementalNewlineDecoder else t.decode("a")))
    class Slots(kind):
        __slots__ = ("extra",)
    s = object.__new__(Slots)
    print("  ", type(s).__name__, answer(lambda: s.extra), answer(lambda: s.closed if kind is not io.IncrementalNewlineDecoder else s.decode("a")))
    for wrong in (int, object, io.BytesIO, io.FileIO):
        print("  ", wrong.__name__, answer(lambda: kind.__new__(wrong)), answer(lambda: wrong.__new__(kind)))
print(io.BytesIO.__new__ is object.__new__, io.StringIO.__new__ is object.__new__, io.FileIO.__new__ is object.__new__,
      "__new__" in vars(io.BytesIO), "__new__" in vars(io.IOBase), io.IOBase.__new__ is object.__new__)
'''


def test_an_allocator_that_is_objects_leaves_the_types_zero_state() -> None:
    same(PROGRAM)


if __name__ == "__main__":
    test_an_allocator_that_is_objects_leaves_the_types_zero_state()
    print("ok")
