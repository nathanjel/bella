"""The slots of a type that CPython's C reads, against a metaclass that would answer for their names (RL-621).

Where a C function asks whether its argument is an index, a buffer, a sequence or a number, it reads a slot of the
argument's type (PyIndex_Check, PyObject_CheckBuffer, tp_as_sequence, tp_as_number): what the classes of the type's MRO
define. The preludes that stand for those functions asked `hasattr(type(x), "__index__")`, which is an attribute lookup
on the class and therefore asks the metaclass: one with a `__getattr__` answered for a slot the type has not, and one
with a property of the name raised for a slot the type has. Review A27 found it in `lru_cache` (RL-616); the same
expression stood in 22 more preludes, 38 times. They ask `_has_slot` now, which reads the classes' own dicts.

The sweep calls each of those functions with an object whose metaclass answers for every special name (CPython: no such
slot, so a TypeError or what the function does with a plain object) and with one whose class defines the methods while
its metaclass raises when asked (CPython: the slot is there and is used). A process for each row, compiled against
CPython: the outcome and what the metaclass was asked for, which is nothing.

Run under pytest or directly: python3 -m pipeline.tests.test_slot_checks
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from pipeline.build import build

SWEEP = r'''
"""Each row calls one function of the standard library whose C reads a slot of its argument's type, with an argument
whose metaclass would answer for the slot's name, or would raise when asked. One row a process: the row's name is argv[1]."""
import binascii
import bisect
import collections
import gc
import grp
import hashlib
import hmac
import io
import math
import pwd
import re
import struct
import sys
import time
import typing
import unicodedata
import zlib
import _imp
import _thread

asked: list[str] = []


class Answers(type):
    """A metaclass that has an answer for every special name: no slot of the class is filled by it."""

    def __getattr__(cls, name: str) -> object:
        if name.startswith("__") and name.endswith("__"):
            asked.append(name)
            return lambda *args: 1
        raise AttributeError(name)


class Fake(metaclass=Answers):
    pass


class Raises(type):
    """A metaclass whose own attributes of the slots' names raise: the class's slots are what its body says."""

    @property
    def __index__(cls) -> object:
        raise ValueError("the metaclass was asked for __index__")

    @property
    def __len__(cls) -> object:
        raise ValueError("the metaclass was asked for __len__")

    @property
    def __getitem__(cls) -> object:
        raise ValueError("the metaclass was asked for __getitem__")

    @property
    def __int__(cls) -> object:
        raise ValueError("the metaclass was asked for __int__")

    @property
    def __float__(cls) -> object:
        raise ValueError("the metaclass was asked for __float__")


class Two(metaclass=Raises):
    """An index of 2, a number of 2.0 and a sequence of [1, 2, 3], by its own methods."""

    def __index__(self) -> int:
        return 2

    def __int__(self) -> int:
        return 2

    def __float__(self) -> float:
        return 2.0

    def __len__(self) -> int:
        return 3

    def __getitem__(self, i: int) -> int:
        return [1, 2, 3][i]


class Raw(io.RawIOBase):
    def __init__(self, answer: object) -> None:
        self.answer = answer

    def readable(self) -> bool:
        return True

    def seekable(self) -> bool:
        return True

    def seek(self, offset: int, whence: int = 0) -> object:   # type: ignore[override]
        return self.answer

    def tell(self) -> object:   # type: ignore[override]
        return self.answer


def rows(x: object) -> dict[str, typing.Callable[[], object]]:
    lock = _thread.allocate_lock()
    return {
        "bisect hi": lambda: bisect.bisect_left([1, 2, 3], 2, 0, x),   # type: ignore[call-overload]
        "bisect sequence": lambda: bisect.bisect_left(x, 2),   # type: ignore[call-overload]
        "insort sequence": lambda: bisect.bisect_right(x, 0, 0, 1),   # type: ignore[call-overload]
        "deque index start": lambda: collections.deque([1, 2, 3]).index(3, x),   # type: ignore[arg-type]
        "lock timeout": lambda: lock.acquire(True, x),   # type: ignore[arg-type]
        "time.gmtime": lambda: time.gmtime(x)[0],   # type: ignore[arg-type]
        "time.sleep": lambda: time.sleep(x),   # type: ignore[arg-type]
        "struct.pack": lambda: struct.pack("i", x),
        "match.group": lambda: re.match("(a)(b)(c)", "abc").group(x),   # type: ignore[union-attr, call-overload]
        "evaluate_bound": lambda: typing.TypeVar("T", bound=int).evaluate_bound(x),   # type: ignore[arg-type]
        "BytesIO.read": lambda: io.BytesIO(b"abcdef").read(x),   # type: ignore[arg-type]
        "BytesIO.seek": lambda: io.BytesIO(b"abcdef").seek(x),   # type: ignore[arg-type]
        "BufferedReader.seek": lambda: io.BufferedReader(Raw(x)).seek(0),
        "FileIO": lambda: io.FileIO(x),   # type: ignore[arg-type]
        "open": lambda: open(x),   # type: ignore[call-overload]  # noqa: SIM115
        "gc.get_objects": lambda: len(gc.get_objects(x)) >= 0,   # type: ignore[arg-type]
        "math.log": lambda: math.log(x),   # type: ignore[arg-type]
        "zlib.crc32": lambda: zlib.crc32(b"abc", x),   # type: ignore[arg-type]
        "grp.getgrgid": lambda: looked_up(lambda: grp.getgrgid(x)),   # type: ignore[arg-type]
        "pwd.getpwuid": lambda: looked_up(lambda: pwd.getpwuid(x)),   # type: ignore[arg-type]
        # the buffer protocol: a class with no buffer slot, whatever its metaclass says
        "binascii.hexlify": lambda: binascii.hexlify(x),   # type: ignore[arg-type]
        "hashlib.md5": lambda: hashlib.md5(x).hexdigest(),   # type: ignore[arg-type]  # noqa: S324
        "hashlib.sha1": lambda: hashlib.sha1(x).hexdigest(),   # type: ignore[arg-type]  # noqa: S324
        "hashlib.sha256": lambda: hashlib.sha256(x).hexdigest(),   # type: ignore[arg-type]
        "hashlib.sha3_256": lambda: hashlib.sha3_256(x).hexdigest(),   # type: ignore[arg-type]
        "hashlib.blake2b": lambda: hashlib.blake2b(x).hexdigest(),   # type: ignore[arg-type]
        "blake2b key": lambda: hashlib.blake2b(b"", key=x).hexdigest(),   # type: ignore[arg-type]
        "hmac.new": lambda: hmac.new(x, b"m", "sha256").hexdigest(),   # type: ignore[arg-type]
        "source_hash": lambda: _imp.source_hash(1, x),   # type: ignore[attr-defined]
        "struct.unpack": lambda: struct.unpack("i", x),   # type: ignore[arg-type]
        "struct.pack_into": lambda: struct.pack_into("i", x, 0, 1),   # type: ignore[arg-type]
        "unicodedata.lookup": lambda: unicodedata.lookup(x),   # type: ignore[arg-type]
        "zlib.compress": lambda: zlib.compress(x),   # type: ignore[arg-type]
        "zlib.decompressobj": lambda: zlib.decompressobj(zdict=x) is not None,   # type: ignore[arg-type]
        "BytesIO": lambda: io.BytesIO(x).getvalue(),   # type: ignore[arg-type]
        "BytesIO.write": lambda: io.BytesIO().write(x),   # type: ignore[arg-type]
        "BytesIO.readinto": lambda: io.BytesIO(b"abc").readinto(x),   # type: ignore[arg-type]
    }


def looked_up(ask: typing.Callable[[], object]) -> str:
    """Whether the number was taken; whether the machine has an entry for it is not the row's matter."""
    try:
        ask()
    except KeyError:
        pass
    return "looked up"


def run(name: str) -> None:
    kind, _, label = name.partition(": ")
    x: object = Fake() if kind == "answers" else Two()
    try:
        outcome = re.sub(r" at 0x[0-9a-f]+", "", repr(rows(x)[label]()))
    except Exception as exc:                     # which exception, by class; its words where they are the program's own
        outcome = type(exc).__name__ + (": " + str(exc) if "metaclass" in str(exc) else "")
    print(name, "|", outcome, "; the metaclass was asked for:", sorted(set(asked)) or "nothing")


if __name__ == "__main__":
    if len(sys.argv) > 1:
        run(sys.argv[1])
    else:
        for kind in ("answers", "raises"):
            for label in rows(None):
                print(kind + ": " + label)
'''


# rows whose function stops by name once its argument is accepted: the row holds that it is accepted
STOPS = {"raises: gc.get_objects": "bella: not implemented: gc.get_objects (CPython's object graph, E-05)"}


def test_a_types_slots_are_read_without_its_metaclass() -> None:
    if shutil.which("g++") is None:
        return
    folder = Path(tempfile.mkdtemp(prefix="bella-slots-"))
    try:
        program = folder / "prog.py"
        program.write_text(SWEEP, encoding="utf-8")
        env = {**os.environ, "PYTHONHASHSEED": "0"}
        listed = subprocess.run([sys.executable, str(program)], capture_output=True, text=True, env=env, cwd=folder, timeout=300)
        assert listed.returncode == 0, listed.stderr
        labels = listed.stdout.splitlines()
        assert len(labels) == 74, len(labels)
        binary = str(build(program, "prog.py", notes=False))
        wrong: list[str] = []
        stopped: list[str] = []
        for label in labels:                     # a process for each row: one that stops takes no other with it
            sides = [subprocess.run([*command, label], capture_output=True, text=True, env=env, cwd=folder, timeout=120, stdin=subprocess.DEVNULL)
                     for command in ([sys.executable, str(program)], [binary])]
            reference, compiled = sides
            assert reference.returncode == 0 and reference.stdout.endswith("; the metaclass was asked for: nothing\n"), (label, reference)
            if compiled.returncode == 70 and compiled.stdout == "" and STOPS.get(label, "\0") in compiled.stderr:
                stopped.append(label)            # the argument was taken as CPython takes it, and the function is one that stops by name
            elif (compiled.returncode, compiled.stdout) != (reference.returncode, reference.stdout):
                wrong.append(f"{label}: compiled {compiled.stdout.strip()!r} (status {compiled.returncode}, {compiled.stderr.strip()[-200:]!r}), "
                             f"CPython {reference.stdout.strip()!r}")
        assert not wrong, "\n".join(wrong)
        assert stopped == list(STOPS), stopped
    finally:
        shutil.rmtree(folder, ignore_errors=True)


if __name__ == "__main__":
    test_a_types_slots_are_read_without_its_metaclass()
    print("ok")
