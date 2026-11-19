"""An exception the C puts in place of another has no trace of it, compiled against CPython.

CPython's C often answers a failure with an error of its own: `PyErr_SetString` over the pending one (struct's "required
argument is not a float", reduce()'s "arg 2 must support iteration"), or `PyErr_Clear` and then an error raised afresh (an
iterator that ends). The new exception's `__context__` is whatever the caller was handling, usually nothing, and
`__suppress_context__` is false. A prelude that wrote the same as `raise New(...) from None` inside the `except` clause
left the first exception in `__context__` (and kept it alive), with `__suppress_context__` true: sixteen places, found
on 2026-11-19 by the sweep of test_deprecated_number_answers.py, where struct's error showed the DeprecationWarning
behind it. They raise outside the handler now. Here is each place that a program can reach, alone and inside a handler
of the program's own, with the whole chain of contexts, the cause and the flag; and what a csv reader raises at the end
of an input whose StopIteration carries a value (a StopIteration of its own, as tp_iternext's NULL gives).

Run under pytest or directly: python3 -m pipeline.tests.test_replaced_exceptions
"""
from __future__ import annotations

from pipeline.tests.test_compiled_imports import same

PLACES = r"""
import csv
import functools
import io
import json
import json.scanner
import os
import struct
import time


class Short:
    def __len__(self):
        return 3

    def __getitem__(self, index):
        raise IndexError(index)


class Stops:
    def __len__(self):
        return 3

    def __getitem__(self, index):
        raise StopIteration(index)


class Breaks:
    def __len__(self):
        return 3

    def __getitem__(self, index):
        raise ZeroDivisionError(index)


class Keys:
    def keys(self):
        return 5

    def values(self):
        return []


class Blocks(io.RawIOBase):
    blocking = True

    def writable(self):
        return True

    def write(self, data):
        return None if self.blocking else len(data)


class GivesInt:
    def __float__(self):
        return 1


class Wide(int):
    pass


class GivesWide:
    def __index__(self):
        return Wide(1)


def blocked():
    raw = Blocks()
    writer = io.BufferedWriter(raw, buffer_size=8)
    try:
        writer.write(b"x" * 8)
        writer.write(b"y" * 20)
    finally:
        raw.blocking = False
        writer.close()


def lines_with_a_value():
    yield "a,b"
    return "the input's value"


def reader_at_the_end():
    reader = csv.reader(lines_with_a_value())
    next(reader)
    try:
        next(reader)
    except StopIteration as stop:
        print("    a reader's end:", stop.args, stop.value)
        raise


SITES = {
    "reversed, IndexError": lambda: next(reversed(Short())),
    "reversed, StopIteration": lambda: next(reversed(Stops())),
    "reversed, another error": lambda: next(reversed(Breaks())),
    "time.gmtime": lambda: time.gmtime(2**70),
    "time.localtime": lambda: time.localtime(2**70),
    "time.sleep": lambda: time.sleep(2**70),
    "time.clock_gettime": lambda: time.clock_gettime("x"),
    "time.clock_gettime, too large": lambda: time.clock_gettime(2**70),
    "posix_spawn env keys": lambda: os.posix_spawn("/bin/true", ["true"], Keys()),
    "posix_spawn file_actions": lambda: os.posix_spawn("/bin/true", ["true"], {}, file_actions=5),
    "csv strict": lambda: next(csv.reader(iter(['"abc']), strict=True)),
    "csv not strict": lambda: next(csv.reader(iter(['"abc']))),
    "csv at the end": reader_at_the_end,
    "csv writerow": lambda: csv.writer(io.StringIO()).writerow(5),
    "structseq": lambda: os.stat_result(5),
    "buffered write blocked": blocked,
    "json scanner": lambda: json.scanner.make_scanner(json.JSONDecoder())("", 0),
    "json raw_decode": lambda: json.JSONDecoder().raw_decode(""),
    "json loads": lambda: json.loads("[1,"),
    "reduce": lambda: functools.reduce(lambda a, b: a, 5),
    "struct float": lambda: struct.pack("<d", "x"),
    "struct float, a wrong answer": lambda: struct.pack("<d", GivesInt()),
    "struct complex": lambda: struct.pack("<D", "x"),
    "struct int too large": lambda: struct.pack("<q", 2**70),
    "struct int, not one": lambda: struct.pack("<q", "x"),
    "struct pack_into": lambda: struct.pack_into("<d", bytearray(8), 0, "x"),
    "struct.Struct.pack": lambda: struct.Struct("<f").pack(None),
}


def chain(exc):
    out = []
    seen = exc.__context__
    while seen is not None and len(out) < 4:
        out.append(type(seen).__name__)
        seen = seen.__context__
    return out


for label, work in SITES.items():
    for outer in (False, True):
        try:
            if outer:
                try:
                    raise KeyError("outer")
                except KeyError:
                    result = work()
            else:
                result = work()
        except BaseException as exc:
            print(label, "| in a handler" if outer else "|", type(exc).__name__, "context", chain(exc), "cause", type(exc.__cause__).__name__,
                  "suppress", exc.__suppress_context__)
        else:
            print(label, "| in a handler" if outer else "|", "no exception:", result)
"""


def test_no_trace_of_the_exception_that_was_replaced() -> None:
    same({"main.py": PLACES}, stderr=True)


if __name__ == "__main__":
    for name, value in sorted(globals().items()):
        if name.startswith("test_") and callable(value):
            value()
    print("ok")
