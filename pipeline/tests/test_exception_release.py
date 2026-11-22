"""What an exception holds goes with it: its arguments, its dict, and the frames its traceback reaches.

Review A35's saved outputs had a stream that was never closed after a method of a buffered reader had refused a write
(RL-802). The cause was not in io: an object of `io.UnsupportedOperation` never let go of its arguments or its traceback,
and the traceback keeps the locals of the frames the exception passed. The runtime gave every class of a prelude a dealloc
of its own (the order a type written in C lets go of its fields, RL-565), and the dealloc of a class over an exception had
no field to name and ended before the exception's own fields. Such a class is no type with a struct of its own: the C makes
it by calling type (`PyErr_NewException`, `_io`'s call of `type`), and its objects die as any class's over that base do.
The model and the header refuse a dealloc of its own over a built-in base with fields; the ten classes of the preludes have
none now.

The sweep is the class: every exception class the modules below have, one object made and dropped, one raised and caught,
one raised through a closure, one kept past its handler.

Run under pytest or directly: python3 -m pipeline.tests.test_exception_release
"""
from __future__ import annotations

from pathlib import Path

from pipeline.tests.test_review_2026_11_19 import same

PROGRAM = (Path(__file__).parent / "exception_release_sweep.txt").read_text()


def test_what_an_exception_holds_goes_with_it() -> None:
    same(PROGRAM)


if __name__ == "__main__":
    test_what_an_exception_holds_goes_with_it()
    print("ok")
