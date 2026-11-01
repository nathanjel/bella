# clause: C-7-12
# spec: section 7
# status: P1
# source: dialect specification section 7, Persistence and compression (zlib is [P1])
"""zlib: round trips, checksums, streaming, and decompression of a fixed stream. Compressed
bytes are not printed: they may differ between zlib implementations at the same level."""
import zlib

data = b"hello hello hello hello " * 20
packed = zlib.compress(data, 9)
print(zlib.decompress(packed) == data, len(packed) < len(data), zlib.crc32(data), zlib.adler32(data), zlib.crc32(b"a", 1))
co = zlib.compressobj(6, zlib.DEFLATED, -15)
raw = co.compress(data) + co.flush()
do = zlib.decompressobj(-15)
print(do.decompress(raw) + do.flush() == data, do.eof, do.unused_data)
fixed = bytes.fromhex("789ccb48cdc9c95728cf2fca4901001a0b045d")
print(zlib.decompress(fixed), zlib.decompress(fixed, bufsize=1))
try:
    zlib.decompress(b"not zlib data")
except zlib.error as exc:
    print("bad stream:", type(exc).__name__)
print(zlib.MAX_WBITS, zlib.Z_BEST_COMPRESSION, isinstance(zlib.ZLIB_VERSION, str))
