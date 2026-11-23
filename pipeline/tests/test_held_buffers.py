"""A buffer argument is held from the argument's parsing to the call's end and read where the C reads it (RL-702, RL-583).

CPython's clinic takes a Py_buffer of a bytes-like argument when it parses the arguments and lets it go at the call's exit; the
work reads the octets through it. So a later argument whose conversion runs the program's code (an `__index__`, a `__bool__`)
can write into a bytearray and the work sees the write, cannot resize it (BufferError: the export), and cannot release the
memoryview it came from (BufferError: the view's own export). The preludes took a copy at the conversion; they now hold the
buffer (`_held`, `_buffer_export`) and read it at the use. `struct.iter_unpack`'s iterator keeps its buffer until it is
exhausted or goes, and reads each step's octets as they are then (RL-583).

`held_buffers.txt` is the class's sweep: every prelude function with a buffer and a later converted argument (zlib's
compress, decompress, crc32, adler32 and its two decompressors, binascii's crc32, hexlify, the base64 and base32 coders,
struct's unpack_from in both forms, blake2's key, salt and person, os.pwrite), each over a bytearray and over a view of one,
and the iterator. Run under pytest or directly: python3 -m pipeline.tests.test_held_buffers
"""
from __future__ import annotations

from pathlib import Path

from pipeline.tests.test_review_2026_11_19 import same

HERE = Path(__file__).resolve().parent


def test_held_buffers() -> None:
    same((HERE / "held_buffers.txt").read_text(encoding="utf-8"))


if __name__ == "__main__":
    test_held_buffers()
    print("ok")
