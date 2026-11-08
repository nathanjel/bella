# clause: C-7-46
# spec: section 7
# status: P1
# source: dialect specification section 7, Modules/zlibmodule.c over zlib 1.3.2 (the pin's, licence entry L-02)
"""The zlib module over zlib 1.3.2 itself: the bytes compress makes at every level, window size and container (zlib, raw, gzip),
decompress with wbits and the auto-detecting values, the error messages the C module builds from zlib's codes, compressobj with
every parameter and a dictionary, Compress.compress and flush with each mode, copies, the states a finished object refuses,
decompressobj with max_length, unconsumed_tail, unused_data, eof and flush, _ZlibDecompressor's buffering with needs_input,
adler32 and crc32 with start values and the combine functions, the constants, the versions and the argument parsing."""
# ruff: noqa: ANN001, ANN002, ANN003, ANN201, ANN202, ANN204, B018, B023, E501, E731, E741, E742, F601, PLR0133, SLF001
import zlib


def m(f):  # type: ignore[no-untyped-def]
    try:
        return repr(f())
    except Exception as e:
        return type(e).__name__ + ": " + str(e)


def h(b):  # type: ignore[no-untyped-def]
    return b.hex() if isinstance(b, bytes) else repr(b)


def gen(n):  # type: ignore[no-untyped-def]
    x = 17 + n
    while True:
        x = (x * 1103515245 + 12345) & 0x7FFFFFFF
        yield x


print("module:", zlib.ZLIB_VERSION, zlib.ZLIB_RUNTIME_VERSION, [n for n in dir(zlib) if not n.startswith("__")], repr(zlib.__doc__)[:60], zlib.error.__module__, zlib.error.__name__, zlib.error.__mro__[1].__name__)
print("constants:", zlib.DEFLATED, zlib.DEF_BUF_SIZE, zlib.DEF_MEM_LEVEL, zlib.MAX_WBITS, zlib.Z_BEST_COMPRESSION, zlib.Z_BEST_SPEED, zlib.Z_BLOCK, zlib.Z_DEFAULT_COMPRESSION, zlib.Z_DEFAULT_STRATEGY, zlib.Z_FILTERED, zlib.Z_FINISH, zlib.Z_FIXED, zlib.Z_FULL_FLUSH, zlib.Z_HUFFMAN_ONLY, zlib.Z_NO_COMPRESSION, zlib.Z_NO_FLUSH, zlib.Z_PARTIAL_FLUSH, zlib.Z_RLE, zlib.Z_SYNC_FLUSH, zlib.Z_TREES)
print("types:", type(zlib.compressobj()).__name__, type(zlib.compressobj()).__module__, type(zlib.decompressobj()).__name__, zlib._ZlibDecompressor.__name__, zlib._ZlibDecompressor.__module__, type(zlib.compressobj()).__doc__, repr(zlib._ZlibDecompressor.__doc__)[:50], m(lambda: type(zlib.compressobj())()), m(lambda: type(zlib.decompressobj())()), [(n, type(getattr(type(zlib.decompressobj()), n)).__name__) for n in sorted(vars(type(zlib.decompressobj()))) if not n.startswith("_")], [(n, type(getattr(zlib._ZlibDecompressor, n)).__name__) for n in sorted(vars(zlib._ZlibDecompressor)) if not n.startswith("_")], type(type(zlib.compressobj()).__copy__).__name__, type(type(zlib.compressobj()).__deepcopy__).__name__)  # type: ignore[attr-defined,no-untyped-call]
print("docs:", repr(zlib.compress.__doc__), repr(zlib.decompress.__doc__), repr(zlib.compressobj.__doc__)[:60], repr(zlib.decompressobj.__doc__), repr(zlib.adler32.__doc__), repr(zlib.crc32.__doc__), repr(zlib.adler32_combine.__doc__)[:50], repr(zlib.crc32_combine.__doc__)[:50], repr(type(zlib.compressobj()).compress.__doc__), repr(type(zlib.compressobj()).flush.__doc__), repr(type(zlib.compressobj()).copy.__doc__), repr(type(zlib.decompressobj()).decompress.__doc__)[:60], repr(type(zlib.decompressobj()).flush.__doc__), repr(type(zlib.decompressobj()).copy.__doc__), repr(zlib._ZlibDecompressor.decompress.__doc__)[:60])  # type: ignore[attr-defined]
g = gen(1)  # type: ignore[no-untyped-call]
text = b"".join(bytes([65 + next(g) % 26]) * (1 + next(g) % 7) for _ in range(300))
binary = bytes(next(g) % 256 for _ in range(2000))
print("compress:", h(zlib.compress(b"")), h(zlib.compress(b"x")), h(zlib.compress(b"hello hello hello hello")), [h(zlib.compress(text, level)) for level in range(-1, 10)], h(zlib.compress(binary))[:80], len(zlib.compress(binary)), [len(zlib.compress(text * 20, level)) for level in (0, 1, 6, 9)])  # type: ignore[no-untyped-call]
print("containers:", h(zlib.compress(text, 6, -15)), h(zlib.compress(text, 6, 31)), h(zlib.compress(text, 6, 9)), h(zlib.compress(text, 6, 25)), h(zlib.compress(text, wbits=-9)), h(zlib.compress(bytearray(text), 1)), h(zlib.compress(b"x" * 100000, 9))[:60], len(zlib.compress(b"x" * 100000, 9)), len(zlib.compress(b"x" * 100000, 0)), h(zlib.compress(b"", wbits=31)))  # type: ignore[no-untyped-call]
for data in (b"", b"x", text, binary, text * 20, b"x" * 100000):
    comp = zlib.compress(data)
    print("round trip", len(data), len(comp), zlib.decompress(comp) == data, zlib.decompress(zlib.compress(data, 9, -15), -15) == data, zlib.decompress(zlib.compress(data, 1, 31), 31) == data, zlib.decompress(comp, 0) == data, zlib.decompress(comp, 47) == data, zlib.decompress(zlib.compress(data, 6, 31), 47) == data, zlib.decompress(comp, 15, 1) == data, zlib.decompress(comp, bufsize=100000) == data, zlib.decompress(bytearray(comp)) == data)
comp = zlib.compress(b"hello")
print("decompress errors:", m(lambda: zlib.decompress(b"x")), m(lambda: zlib.decompress(comp[:-2])), m(lambda: zlib.decompress(comp + b"junk")), m(lambda: zlib.decompress(b"")), m(lambda: zlib.decompress(comp, -15)), m(lambda: zlib.decompress(zlib.compress(b"hello", wbits=-15), -15)), m(lambda: zlib.decompress(comp, 7)), m(lambda: zlib.decompress(comp, 15, -1)), m(lambda: zlib.decompress(comp, 15, 0)), m(lambda: zlib.decompress(comp, 15, 1.5)), m(lambda: zlib.decompress(zlib.compress(b"hello", wbits=31), 15)), m(lambda: zlib.decompress(comp, 31)), m(lambda: zlib.decompress(b"\x78\x9c" + b"\xff" * 10)), m(lambda: zlib.decompress(comp[:2])), m(lambda: zlib.decompress(comp[:-1])), m(lambda: zlib.decompress(comp[:-1] + bytes([comp[-1] ^ 1]))), m(lambda: zlib.decompress(comp, 15, 2**70)), m(lambda: zlib.decompress(comp, 2**40)), m(lambda: zlib.decompress("x")), m(lambda: zlib.decompress()), m(lambda: zlib.decompress(comp, 15, 1, 2)), m(lambda: zlib.decompress(comp, bogus=1)), m(lambda: zlib.decompress(data=comp)), m(lambda: zlib.decompress(comp, wbits=-15, bufsize=0)))  # type: ignore[arg-type,call-arg,no-untyped-call]
print("compress errors:", m(lambda: zlib.compress(b"x", 10)), m(lambda: zlib.compress(b"x", -2)), m(lambda: zlib.compress(b"x", 9, 7)), m(lambda: zlib.compress(b"x", wbits=0)), m(lambda: zlib.compress(b"x", wbits=-16)), m(lambda: zlib.compress(b"x", wbits=32)), m(lambda: zlib.compress("x")), m(lambda: zlib.compress(b"x", 1.5)), m(lambda: zlib.compress(b"x", 2**40)), m(lambda: zlib.compress()), m(lambda: zlib.compress(b"x", 1, 15, 2)), m(lambda: zlib.compress(data=b"x")), m(lambda: zlib.compress(b"x", level=1, wbits=-15).hex()), m(lambda: zlib.compress(b"x", bogus=1)), m(lambda: zlib.compress(b"x", 1, level=2)), m(lambda: zlib.compress(None)), m(lambda: zlib.compress([1, 2])))  # type: ignore[arg-type,call-arg,misc,no-untyped-call]
co = zlib.compressobj(9, zlib.DEFLATED, -15, 9, zlib.Z_FILTERED)
print("compressobj:", h(co.compress(text)), h(co.compress(b"")), h(co.flush(zlib.Z_SYNC_FLUSH)), h(co.flush(zlib.Z_NO_FLUSH)), h(co.flush(zlib.Z_FULL_FLUSH)), h(co.compress(binary[:100])), h(co.flush(zlib.Z_PARTIAL_FLUSH)), h(co.flush(zlib.Z_BLOCK)), h(co.flush()), m(lambda: co.flush()), m(lambda: co.compress(b"x")), m(lambda: co.copy()), m(lambda: co.flush(zlib.Z_SYNC_FLUSH)))  # type: ignore[no-untyped-call]
co = zlib.compressobj()
part = co.compress(text)
cp = co.copy()
print("copies:", h(part), h(co.flush()), h(cp.compress(text[:10]) + cp.flush()), type(cp).__name__, cp is not co, h(cp.__copy__().flush()) if False else "skip", m(lambda: cp.copy()), m(lambda: cp.__copy__()), m(lambda: cp.__deepcopy__({})), m(lambda: cp.__deepcopy__()), m(lambda: cp.__deepcopy__(1, 2)), m(lambda: cp.copy(1)), m(lambda: cp.copy(x=1)), m(lambda: cp.__copy__(1)))  # type: ignore[call-arg,no-untyped-call]
whole = zlib.compress(text)
pieces = zlib.compressobj()
piecewise = b"".join(pieces.compress(text[i:i + 37]) for i in range(0, len(text), 37)) + pieces.flush()
print("piecewise:", piecewise == whole, h(piecewise)[:40], zlib.decompress(piecewise) == text)  # type: ignore[no-untyped-call]
for kw in ({"level": 0}, {"level": 1, "strategy": zlib.Z_HUFFMAN_ONLY}, {"level": 9, "strategy": zlib.Z_RLE}, {"level": 6, "strategy": zlib.Z_FIXED}, {"wbits": 8}, {"wbits": 9}, {"wbits": 31}, {"wbits": -9}, {"memLevel": 1}, {"memLevel": 9}, {"zdict": b"hello world"}, {"wbits": -15, "zdict": text[:50]}, {"level": 3, "method": zlib.DEFLATED, "wbits": 12, "memLevel": 5, "strategy": zlib.Z_FILTERED, "zdict": b"ABCDEFG"}):
    c = zlib.compressobj(**kw)
    out = c.compress(text) + c.flush()
    wb = kw.get("wbits", 15)
    wb = wb if wb < 0 or wb >= 25 else 15  # type: ignore[operator]  # a small positive window is read with the default: inflate takes any smaller one
    d = zlib.decompressobj(wbits=wb, zdict=kw["zdict"]) if "zdict" in kw else zlib.decompressobj(wb)  # type: ignore[arg-type]
    print("  obj", sorted(kw.items(), key=lambda kv: kv[0]), h(out)[:50], len(out), d.decompress(out) == text, d.eof, h(d.unused_data), h(d.unconsumed_tail))  # type: ignore[no-untyped-call]
print("compressobj errors:", m(lambda: zlib.compressobj(level=10)), m(lambda: zlib.compressobj(method=9)), m(lambda: zlib.compressobj(memLevel=0)), m(lambda: zlib.compressobj(memLevel=10)), m(lambda: zlib.compressobj(strategy=9)), m(lambda: zlib.compressobj(wbits=7)), m(lambda: zlib.compressobj(wbits=16)), m(lambda: zlib.compressobj(wbits=32)), m(lambda: zlib.compressobj(zdict="abc")), m(lambda: zlib.compressobj(zdict=5)), m(lambda: zlib.compressobj(1, 2, 3, 4, 5, b"", 7)), m(lambda: zlib.compressobj(bogus=1)), m(lambda: zlib.compressobj(1, level=1)), m(lambda: zlib.compressobj(level=2**40)), m(lambda: zlib.compressobj(level=1.5)), m(lambda: zlib.compressobj(level=None)), m(lambda: zlib.compressobj(wbits=-15, zdict=b"").compress(b"a").hex()))  # type: ignore[arg-type,call-arg,misc,no-untyped-call]
co = zlib.compressobj()
print("compress methods:", m(lambda: co.compress()), m(lambda: co.compress(b"", b"")), m(lambda: co.compress(data=b"")), m(lambda: co.compress("x")), m(lambda: co.flush(1, 2)), m(lambda: co.flush(mode=1)), m(lambda: co.flush(1.5)), m(lambda: co.flush(2**40)), m(lambda: co.flush(7)), m(lambda: co.copy(1)), m(lambda: co.copy(x=1)), m(lambda: co.__copy__(1)), m(lambda: co.__deepcopy__()), m(lambda: co.__deepcopy__({}) is not co), m(lambda: co.__deepcopy__(1, 2)))  # type: ignore[arg-type,call-arg,no-untyped-call]
d = zlib.decompressobj()
c = zlib.compress(b"abc" * 100)  # type: ignore[assignment]
print("decompressobj:", h(d.decompress(c[:10], 5)), h(d.unconsumed_tail), d.eof, len(d.decompress(d.unconsumed_tail + c[10:] + b"tail")), h(d.unused_data), d.eof, h(d.unconsumed_tail), h(d.flush()), m(lambda: d.decompress(b"more")), h(d.unused_data), m(lambda: d.copy()), m(lambda: d.flush(0)), m(lambda: d.flush(-1)), m(lambda: d.decompress(b"", -1)), h(d.flush()), h(d.flush(5)))  # type: ignore[index,no-untyped-call]
d = zlib.decompressobj()
chunks = []
rest = c
while rest:
    out = d.decompress(rest, 7)  # type: ignore[arg-type]
    chunks.append((len(out), len(d.unconsumed_tail), d.eof))
    rest = d.unconsumed_tail  # type: ignore[assignment]
print("by sevens:", chunks[:5], chunks[-3:], len(chunks), h(d.flush()), d.eof, h(d.unused_data))  # type: ignore[unreachable]
d = zlib.decompressobj()
print("tail then flush:", h(d.decompress(c[:20], 3)), len(d.unconsumed_tail), h(d.flush(1)[:10]), len(d.flush()), d.eof, m(lambda: h(d.decompress(c[20:])[:10])), d.eof, h(d.unconsumed_tail), m(lambda: h(d.flush())), d.eof, m(lambda: d.decompress(b"x")))
d = zlib.decompressobj()
print("flush variants:", h(d.decompress(c[:5])), d.eof, h(d.flush()), d.eof, m(lambda: h(d.decompress(c[5:])[:12])), d.eof, m(lambda: h(d.flush())), m(lambda: d.flush()), m(lambda: d.copy()))
d = zlib.decompressobj()
d2 = d.copy()
print("decompress copies:", h(d.decompress(c[:15])), h(d2.decompress(c[:15])), d.copy().decompress(c[15:]) == d2.copy().decompress(c[15:]), h(d.__copy__().decompress(c[15:])[-6:]), h(d.__deepcopy__({}).decompress(c[15:])[-6:]), m(lambda: d.copy(1)), m(lambda: d.__deepcopy__()), type(d.copy()).__name__, d.copy().eof, h(d.copy().unconsumed_tail))
print("decompress methods:", m(lambda: d.decompress()), m(lambda: d.decompress(c, 1, 2)), m(lambda: d.decompress(data=c)), m(lambda: d.decompress(c, bogus=5)), m(lambda: d.decompress(c, max_length=-1)), m(lambda: d.decompress(c, 2**70)), m(lambda: d.decompress(c, 1.5)), m(lambda: d.decompress("x")), m(lambda: d.flush(length=5)), m(lambda: d.flush(1, 2)), m(lambda: d.flush(1.5)), m(lambda: d.flush(2**70)), m(lambda: setattr(d, "eof", 1)), m(lambda: setattr(d, "unused_data", 1)), m(lambda: setattr(d, "unconsumed_tail", 1)), m(lambda: setattr(d, "x", 1)))
print("decompressobj errors:", m(lambda: zlib.decompressobj(zdict=5)), m(lambda: zlib.decompressobj(wbits=100)), m(lambda: zlib.decompressobj(wbits=7)), m(lambda: zlib.decompressobj(1, 2, 3)), m(lambda: zlib.decompressobj(wbits=1.5)), m(lambda: zlib.decompressobj(bogus=1)), m(lambda: zlib.decompressobj(zdict=bytearray(b"x")).unused_data), m(lambda: zlib.decompressobj().decompress(b"x")), m(lambda: zlib.decompressobj().decompress(b"\x78\x9c\xff\xff")), m(lambda: zlib.decompressobj(-15).decompress(b"\xff\xff\xff\xff")), m(lambda: zlib.decompressobj(-15).decompress(c)), m(lambda: zlib.decompressobj(31).decompress(c)))
cz = zlib.compressobj(zdict=b"hello world")
dict_stream = cz.compress(b"hello world hello world") + cz.flush()
print("dictionary:", h(dict_stream), m(lambda: zlib.decompressobj().decompress(dict_stream)), m(lambda: zlib.decompressobj(zdict=b"wrong dict").decompress(dict_stream)), m(lambda: zlib.decompressobj(zdict=b"hello world").decompress(dict_stream)), m(lambda: zlib.decompress(dict_stream)), m(lambda: zlib.decompressobj(wbits=-15, zdict=b"hello world").decompress(zlib.compressobj(wbits=-15, zdict=b"hello world").compress(b"hello world!") + zlib.compressobj(wbits=-15, zdict=b"hello world").flush())))
z = zlib._ZlibDecompressor()
cb = zlib.compress(binary)
print("zlibdecompressor:", z.eof, z.needs_input, h(z.unused_data), h(z.decompress(cb[:10])), z.needs_input, z.eof, h(z.decompress(cb[10:200], 5)), z.needs_input, h(z.decompress(b"", 5)), z.needs_input, len(z.decompress(b"", 1000)), z.needs_input, len(z.decompress(cb[200:] + b"trail")), z.eof, z.needs_input, h(z.unused_data), m(lambda: z.decompress(b"x")), m(lambda: z.decompress(b"")), len(cb))
z = zlib._ZlibDecompressor()
total = b""
steps = []
for i in range(0, len(cb), 300):
    out = z.decompress(cb[i:i + 300], 500)
    total += out
    steps.append((len(out), z.needs_input, z.eof))
    while not z.needs_input and not z.eof:
        out = z.decompress(b"", 500)
        total += out
        steps.append((len(out), z.needs_input, z.eof))
print("zlibdecompressor steps:", total == binary, steps, h(z.unused_data))
z = zlib._ZlibDecompressor(wbits=-15)
raw = zlib.compress(b"abc" * 50, 6, -15)
print("zlibdecompressor raw:", h(z.decompress(raw[:5], 4)), z.needs_input, h(z.decompress(raw[5:], 0)), z.needs_input, len(z.decompress(b"", 100)), len(z.decompress(b"", -1)), z.eof, z.needs_input, h(z.unused_data))
z = zlib._ZlibDecompressor(zdict=b"hello world")
print("zlibdecompressor dict:", m(lambda: zlib._ZlibDecompressor(wbits=-15, zdict=b"hello world").decompress(zlib.compressobj(wbits=-15, zdict=b"hello world").compress(b"hello world!") + zlib.compressobj(wbits=-15, zdict=b"hello world").flush())), m(lambda: zlib._ZlibDecompressor(1, 2, 3)), m(lambda: zlib._ZlibDecompressor(bogus=1)), m(lambda: zlib._ZlibDecompressor(wbits=100)), m(lambda: type(zlib._ZlibDecompressor(zdict="x")).__name__), m(lambda: zlib._ZlibDecompressor().decompress()), m(lambda: zlib._ZlibDecompressor().decompress(max_length=1)), m(lambda: zlib._ZlibDecompressor().decompress(b"", 1, 2)), m(lambda: zlib._ZlibDecompressor().decompress(data=b"x", max_length=-5)), m(lambda: zlib._ZlibDecompressor().decompress(b"", 1.5)), m(lambda: zlib._ZlibDecompressor().decompress(b"garbage!")), m(lambda: setattr(zlib._ZlibDecompressor(), "eof", 1)), m(lambda: setattr(zlib._ZlibDecompressor(), "unused_data", 1)), m(lambda: zlib._ZlibDecompressor().decompress(c[:5], 2**70)))
print("checksums:", zlib.adler32(b""), zlib.adler32(b"hello"), zlib.adler32(text), zlib.adler32(binary), zlib.adler32(b"hello", 0), zlib.adler32(b"hello", 12345), zlib.adler32(bytearray(b"hello")), zlib.crc32(b""), zlib.crc32(b"hello"), zlib.crc32(text), zlib.crc32(binary), zlib.crc32(b"hello", 12345), zlib.crc32(b"hello", 2**32 - 1), zlib.adler32(b"hello", 2**32 - 1), zlib.crc32(b"x" * 10000), zlib.adler32(b"x" * 10000))
print("combine:", zlib.adler32_combine(zlib.adler32(text), zlib.adler32(binary), len(binary)) == zlib.adler32(text + binary), zlib.crc32_combine(zlib.crc32(text), zlib.crc32(binary), len(binary)) == zlib.crc32(text + binary), zlib.adler32_combine(1, 1, 0), zlib.crc32_combine(0, 0, 0), zlib.crc32_combine(123, 456, 789), zlib.adler32_combine(123, 456, 789), zlib.adler32_combine(zlib.adler32(b"ab"), zlib.adler32(b"cd"), 2) == zlib.adler32(b"abcd"))
print("checksum errors:", m(lambda: zlib.adler32()), m(lambda: zlib.adler32(data=b"")), m(lambda: zlib.adler32(b"", 1, 2)), m(lambda: zlib.adler32("x")), m(lambda: zlib.crc32(b"a", 1.5)), m(lambda: zlib.crc32(b"a", True)), m(lambda: zlib.crc32_combine(1, 2)), m(lambda: zlib.crc32_combine(1, 2, 3, 4)), m(lambda: zlib.crc32_combine(a=1)), m(lambda: zlib.adler32_combine(1.5, 2, 3)), m(lambda: zlib.crc32_combine(1, 2, -1)), m(lambda: zlib.crc32_combine(1, 2, 2**70)), m(lambda: zlib.crc32_combine(1, 2, 1.5)), m(lambda: zlib.crc32_combine(1, 2, True)))
