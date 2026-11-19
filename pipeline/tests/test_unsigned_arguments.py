"""An argument the C takes as an unsigned field of bits, compiled against CPython (C-7-90).

The clinic's unsigned_int(bitwise=True) and unsigned_long(bitwise=True) take the int's low bits. 3.15 reads it with
PyLong_AsNativeBytes and warns ("integer value out of range", a DeprecationWarning) when the int needs more bytes than the
field has, as an unsigned number or as a signed one; so 2**32 warns for a 32-bit field and -1 does not. The runtime has
five such arguments: the start value of zlib.crc32 and zlib.adler32 and of binascii.crc32, the flags of os.memfd_create
and the thread id of signal.pthread_kill, and the two crcs and adlers of zlib's combine functions. Until 2026-11-19 zlib
and binascii stopped by name for every start value outside 0..2**32-1, -1 among them, which CPython takes without a word.

Run under pytest or directly: python3 -m pipeline.tests.test_unsigned_arguments
"""
from __future__ import annotations

from pipeline.tests.test_compiled_imports import same

FIELDS = r"""
import binascii
import os
import signal
import threading
import warnings
import zlib


class Index:
    def __init__(self, value):
        self.value = value

    def __index__(self):
        return self.value


class Wide(int):
    pass


VALUES = [0, 1, 2**31 - 1, 2**31, 2**32 - 1, 2**32, 2**32 + 5, 2**63, 2**64 - 1, 2**64, 2**64 + 7, 2**100,
          -1, -2, -2**31, -2**31 - 1, -2**32, -2**32 - 1, -2**63, -2**63 - 1, -2**64, -2**100,
          True, False, Wide(2**32 + 1), Index(7), Index(2**32 + 9), Index(-2**31 - 3), Index(True), 1.5, "1", None, b"1", [1]]


def memfd(flags):
    fd = os.memfd_create("probe", flags)
    os.close(fd)
    return "made"


SITES = {
    "binascii.crc32": lambda v: binascii.crc32(b"abc", v),
    "binascii.crc32 by name": lambda v: binascii.crc32(b"abc", crc=v),
    "zlib.crc32": lambda v: zlib.crc32(b"abc", v),
    "zlib.adler32": lambda v: zlib.adler32(b"abc", v),
    "zlib.crc32_combine 1": lambda v: zlib.crc32_combine(v, 5, 3),
    "zlib.crc32_combine 2": lambda v: zlib.crc32_combine(5, v, 3),
    "zlib.adler32_combine 1": lambda v: zlib.adler32_combine(v, 5, 3),
    "zlib.adler32_combine 2": lambda v: zlib.adler32_combine(5, v, 3),
    "os.memfd_create": memfd,
}

for name, site in SITES.items():
    for v in VALUES:
        shown = f"Index({v.value})" if isinstance(v, Index) else repr(v)
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            try:
                out = repr(site(v))
            except Exception as exc:
                out = "raised " + type(exc).__name__ + ": " + str(exc)
        print(f"{name}({shown}) -> {out} {[(w.category.__name__, str(w.message), w.lineno) for w in caught]}")
        with warnings.catch_warnings():
            warnings.simplefilter("error")
            try:
                site(v)
            except DeprecationWarning:
                print("    as an error: DeprecationWarning")
            except Exception:
                pass

# a thread's id with what an unsigned long drops: the same thread (an id that is no thread's is not to be tried)
me = threading.get_ident()
for label, ident in (("its id", me), ("its id and 2**64", me + 2**64), ("its id less 2**64", me - 2**64), ("its id and 2**70", me + 2**70)):
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        try:
            out = repr(signal.pthread_kill(ident, 0))
        except Exception as exc:
            out = "raised " + type(exc).__name__ + ": " + str(exc)
    print(f"signal.pthread_kill({label}) -> {out} {[(w.category.__name__, str(w.message)) for w in caught]}")
"""

# ast's abstract node classes (C-7-91): every node class called with nothing, and what a program derives from them
NODES = r"""
import ast
import warnings

for name in sorted(dir(ast)):
    cls = getattr(ast, name)
    if isinstance(cls, type) and issubclass(cls, ast.AST):
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            try:
                out = type(cls()).__name__
            except TypeError as exc:
                out = "TypeError: " + str(exc)
        print(name, out, [(w.category.__name__, str(w.message), w.lineno) for w in caught], ast._is_abstract(cls) if hasattr(ast, "_is_abstract") else "")


class Mine(ast.stmt):
    _fields = ("value",)


class expr(ast.expr):
    pass


expr.__module__ = "ast"
for cls, args, kwds in ((Mine, (1,), {}), (expr, (), {}), (ast.expr, (), {"lineno": 2}), (ast.stmt, (5,), {}), (ast.mod, (), {"zzz": 1})):
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        try:
            out = type(cls(*args, **kwds)).__name__
        except TypeError as exc:
            out = "TypeError: " + str(exc)
    print(cls.__name__, out, [(w.category.__name__, str(w.message)) for w in caught])
with warnings.catch_warnings():
    warnings.simplefilter("error")
    try:
        ast.operator()
    except DeprecationWarning as exc:
        print("as an error:", exc)
"""


def test_a_field_of_bits_takes_any_int() -> None:
    same({"main.py": FIELDS})


def test_abstract_node_classes_warn() -> None:
    same({"main.py": NODES})


if __name__ == "__main__":
    for name, value in sorted(globals().items()):
        if name.startswith("test_") and callable(value):
            value()
    print("ok")
