# clause: C-7-90
# spec: section 7 (zlib, binascii, os, signal, warnings)
# status: P1
# source: Python/getargs.c and the clinic's unsigned_int(bitwise=True) and unsigned_long(bitwise=True) (PyLong_AsNativeBytes
#         with Py_ASNATIVEBYTES_UNSIGNED_BUFFER, then "integer value out of range"), Modules/zlibmodule.c, Modules/binascii.c,
#         Modules/posixmodule.c (os_memfd_create), Modules/signalmodule.c (signal_pthread_kill)
"""An argument that C takes as an unsigned field of bits: the start value of a checksum, the flags of memfd_create, a
thread's id. An int that the field holds, as an unsigned number or as a signed one, is taken as it is; any other is cut
to the field's bits, as before 3.15, and 3.15 warns that this will end. What is no int fails as an index does."""
import binascii
import os
import signal
import threading
import warnings
import zlib
from collections.abc import Callable


class Index:
    def __init__(self, value: int) -> None:
        self.value = value

    def __index__(self) -> int:
        return self.value


def flags_of_memfd(flags: object) -> str:
    try:
        made = os.memfd_create("a name", flags)  # type: ignore[arg-type]
    except OSError:
        return "the system refuses the flags"
    os.close(made)
    return "made"


FIELDS: list[tuple[str, Callable[[object], object]]] = [
    ("zlib.crc32", lambda start: zlib.crc32(b"abc", start)),  # type: ignore[arg-type]
    ("zlib.adler32", lambda start: zlib.adler32(b"abc", start)),  # type: ignore[arg-type]
    ("binascii.crc32", lambda start: binascii.crc32(b"abc", start)),  # type: ignore[arg-type]
    ("os.memfd_create", flags_of_memfd),
]
VALUES: list[tuple[str, object]] = [
    ("0", 0), ("2**31", 2**31), ("2**32 - 1", 2**32 - 1), ("2**32", 2**32), ("2**32 + 5", 2**32 + 5), ("2**64 + 7", 2**64 + 7),
    ("-1", -1), ("-2**31", -2**31), ("-2**31 - 1", -2**31 - 1), ("-2**32", -2**32), ("-2**70", -2**70),
    ("True", True), ("an index of 7", Index(7)), ("an index of 2**32 + 9", Index(2**32 + 9)), ("1.5", 1.5), ("a str", "1"), ("None", None),
]

for name, field in FIELDS:
    for label, value in VALUES:
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            try:
                out = repr(field(value))
            except TypeError:
                out = "TypeError"
        said = [f"{w.category.__name__}: {w.message}, line {w.lineno}" for w in caught]
        with warnings.catch_warnings():
            warnings.simplefilter("error")
            try:
                field(value)
                as_error = ""
            except DeprecationWarning:
                as_error = " | as an error it is raised"
            except TypeError:
                as_error = ""
        print(f"{name}({label}): {out} {said}{as_error}")

# a thread's id is an unsigned long: what 64 bits drop is this thread still
me = threading.get_ident()
for label, ident in (("its id", me), ("its id and 2**64", me + 2**64), ("its id less 2**64", me - 2**64), ("its id and 2**70", me + 2**70)):
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        signal.pthread_kill(ident, 0)
    print(f"signal.pthread_kill({label}): sent {[f'{w.category.__name__}: {w.message}' for w in caught]}")
