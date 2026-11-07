"""zlib, the shape of it: the protocol's constants, `error`, and every function stopping by name until the library behind it is settled
(licence entry L-02: zlib itself, or miniz). `shutil` and `argparse` need the import; `ZLIB_VERSION` and `ZLIB_RUNTIME_VERSION`, which
would describe a library, stop by name when read (a module __getattr__)."""

__all__ = ["DEFLATED", "DEF_BUF_SIZE", "DEF_MEM_LEVEL", "MAX_WBITS", "Z_BEST_COMPRESSION", "Z_BEST_SPEED", "Z_BLOCK", "Z_DEFAULT_COMPRESSION",
           "Z_DEFAULT_STRATEGY", "Z_FILTERED", "Z_FINISH", "Z_FIXED", "Z_FULL_FLUSH", "Z_HUFFMAN_ONLY", "Z_NO_COMPRESSION", "Z_NO_FLUSH",
           "Z_PARTIAL_FLUSH", "Z_RLE", "Z_SYNC_FLUSH", "Z_TREES", "__getattr__", "_ZlibDecompressor", "adler32", "adler32_combine", "compress",
           "compressobj", "crc32", "crc32_combine", "decompress", "decompressobj", "error"]

__name__ = "zlib"

try:
    _bella_refuse                                # noqa: B018  # a facility phase 1 lacks, where it would run
except NameError:
    from collections.abc import Callable
    from typing import Any

    def _missing(*args: object) -> Any:
        raise ImportError("this file needs the runtime's primitives")

    _bella_refuse: Callable[..., Any] = _missing

DEFLATED = 8
DEF_BUF_SIZE = 16384
DEF_MEM_LEVEL = 8
MAX_WBITS = 15
Z_BEST_COMPRESSION = 9
Z_BEST_SPEED = 1
Z_BLOCK = 5
Z_DEFAULT_COMPRESSION = -1
Z_DEFAULT_STRATEGY = 0
Z_FILTERED = 1
Z_FINISH = 4
Z_FIXED = 4
Z_FULL_FLUSH = 3
Z_HUFFMAN_ONLY = 2
Z_NO_COMPRESSION = 0
Z_NO_FLUSH = 0
Z_PARTIAL_FLUSH = 1
Z_RLE = 3
Z_SYNC_FLUSH = 2
Z_TREES = 6


class error(Exception):  # noqa: N801
    pass


error.__module__ = "zlib"

_WHY = " (zlib: the library behind it is licence entry L-02, still open)"


def _unwritten(name: str) -> object:
    def unwritten(*args: object, **kwds: object) -> None:
        _bella_refuse("zlib." + name + _WHY)
    unwritten.__name__ = unwritten.__qualname__ = name
    return unwritten


def __getattr__(name: str) -> object:
    if name in ("ZLIB_VERSION", "ZLIB_RUNTIME_VERSION"):
        _bella_refuse("zlib." + name + _WHY)
    raise AttributeError("module 'zlib' has no attribute '" + name + "'")


adler32 = _unwritten("adler32")
adler32_combine = _unwritten("adler32_combine")
compress = _unwritten("compress")
compressobj = _unwritten("compressobj")
crc32 = _unwritten("crc32")
crc32_combine = _unwritten("crc32_combine")
decompress = _unwritten("decompress")
decompressobj = _unwritten("decompressobj")
_ZlibDecompressor = _unwritten("_ZlibDecompressor")
