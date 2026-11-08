# clause: C-7-35
# spec: section 7
# status: P1
# source: dialect specification section 7, Modules/binascii.c, Lib/base64.py
"""binascii: base64 both ways with 3.15's parameters (padded, wrapcol, newline, alphabet; strict_mode, ignorechars, canonical) and every
message of the strict decoder, hex both ways with separators and ignorechars, crc32 incrementally and with a masked seed, the clinic's
converters (an ASCII str or a bytes-like object, size_t, bytes), the two exceptions; base64's functions over them."""
# ruff: noqa: ANN001, ANN002, ANN003, ANN201, ANN202, ANN204, B018, B023, E501, E731, E741, E742, F601, PLR0133, SLF001
import base64
import binascii


def failed(f):  # type: ignore[no-untyped-def]
    try:
        return f()
    except Exception as exc:
        return (type(exc).__name__, exc.args)


print(binascii.Error.__mro__[1:3], binascii.Incomplete.__mro__[1], binascii.Error.__module__, binascii.Error.__name__, binascii.Error.__qualname__)
print(len(binascii.BASE64_ALPHABET), binascii.URLSAFE_BASE64_ALPHABET[-2:], binascii.BASE32_ALPHABET, len(binascii.ASCII85_ALPHABET), len(binascii.Z85_ALPHABET))

# ---- b2a_base64 ----
for data in (b"", b"f", b"fo", b"foo", b"foob", b"fooba", b"foobar", bytes(range(256))[:48], b"\xff\xfe\xfd"):
    print(binascii.b2a_base64(data), binascii.b2a_base64(data, newline=False), binascii.b2a_base64(data, padded=False), binascii.b2a_base64(data, newline=False, padded=False))
long = bytes(range(70))
for wrapcol in (0, 1, 3, 4, 5, 8, 76, 80, 95, 96, 1000):
    print(wrapcol, binascii.b2a_base64(long, wrapcol=wrapcol), binascii.b2a_base64(long, wrapcol=wrapcol, newline=False, padded=False))
print(binascii.b2a_base64(b"\xfb\xff", alphabet=binascii.URLSAFE_BASE64_ALPHABET), binascii.b2a_base64(bytearray(b"hi"), alphabet=bytearray(binascii.BASE64_ALPHABET[::-1])))
print(failed(lambda: binascii.b2a_base64(b"x", alphabet=b"abc")), failed(lambda: binascii.b2a_base64(b"x", alphabet="a" * 64)), failed(lambda: binascii.b2a_base64("x")),  # type: ignore[arg-type,no-untyped-call]
      failed(lambda: binascii.b2a_base64(b"x", wrapcol=-1)), failed(lambda: binascii.b2a_base64(b"x", wrapcol=1.5)), failed(lambda: binascii.b2a_base64(b"x", wrapcol=2**70)),  # type: ignore[arg-type,no-untyped-call]
      failed(lambda: binascii.b2a_base64(b"x", padded=0, newline=[], wrapcol=True)), failed(lambda: binascii.b2a_base64(b"x", True)), failed(lambda: binascii.b2a_base64()), failed(lambda: binascii.b2a_base64(b"x", nl=1)))  # type: ignore[arg-type,call-arg,no-untyped-call]

# ---- a2b_base64 ----
for text in (b"", b"Zg==", b"Zm8=", b"Zm9v", b"Zm9vYg==", b"Zm9vYmE=", b"Zm9vYmFy", b"Zm9v\nYmFy\n", b"Zm 9v", b"Zg=", b"Zg", b"Z", b"Zg==Zg==", b"Zg==x", b"Zg=x=", b"=Zg==", b"Zm9v====", b"Z=g==", b"Zh==", b"Zm9vYmF="):
    print(text, failed(lambda: binascii.a2b_base64(text)), failed(lambda: binascii.a2b_base64(text, strict_mode=True)), failed(lambda: binascii.a2b_base64(text, padded=False)),  # type: ignore[no-untyped-call]
          failed(lambda: binascii.a2b_base64(text, strict_mode=True, padded=False)), failed(lambda: binascii.a2b_base64(text, canonical=True)))  # type: ignore[no-untyped-call]
print(failed(lambda: binascii.a2b_base64(b"Zm 9v\n", ignorechars=b" \n")), failed(lambda: binascii.a2b_base64(b"Zm 9v\n", ignorechars=b" ")), failed(lambda: binascii.a2b_base64(b"Zm 9v", ignorechars=b"")),  # type: ignore[no-untyped-call]
      failed(lambda: binascii.a2b_base64(b"Zm 9v", strict_mode=False, ignorechars=b"x")), failed(lambda: binascii.a2b_base64(b"Zg==x", ignorechars=b"x")), failed(lambda: binascii.a2b_base64(b"Zg=x=", ignorechars=b"=")),  # type: ignore[no-untyped-call]
      failed(lambda: binascii.a2b_base64(b"=Zg==", ignorechars=b"=")), failed(lambda: binascii.a2b_base64(b"Zg==Zg==", ignorechars=b"=")))  # type: ignore[no-untyped-call]
print(binascii.a2b_base64("Zm9v"), binascii.a2b_base64(bytearray(b"Zm9v")), binascii.a2b_base64(b"-_8=", alphabet=binascii.URLSAFE_BASE64_ALPHABET), failed(lambda: binascii.a2b_base64(b"+/8=", alphabet=binascii.URLSAFE_BASE64_ALPHABET, strict_mode=True)),  # type: ignore[no-untyped-call]
      failed(lambda: binascii.a2b_base64(b"+/8=", alphabet=binascii.URLSAFE_BASE64_ALPHABET)), binascii.a2b_base64(b"Zg==", alphabet=bytes(binascii.BASE64_ALPHABET)))  # type: ignore[no-untyped-call]
print(failed(lambda: binascii.a2b_base64("Zm9v\xe9")), failed(lambda: binascii.a2b_base64(1)), failed(lambda: binascii.a2b_base64(b"Zg==", alphabet="A" * 64)), failed(lambda: binascii.a2b_base64(b"Zg==", alphabet=bytearray(64))),  # type: ignore[arg-type,no-untyped-call]
      failed(lambda: binascii.a2b_base64(b"Zg==", alphabet=b"short")), failed(lambda: binascii.a2b_base64(b"Zg==", ignorechars="x")), failed(lambda: binascii.a2b_base64(b"Zg==", True)))  # type: ignore[arg-type,call-arg,no-untyped-call]

print(type(binascii.a2b_base64(bytearray(b"Zg=="))), type(binascii.b2a_base64(bytearray(b"x"))), type(binascii.crc32(bytearray())))

# ---- hex ----
for data in (b"", b"\xb9\x01\xef", bytes(range(10))):
    print(binascii.hexlify(data), binascii.b2a_hex(data), binascii.hexlify(data, ":"), binascii.hexlify(data, b"_", 2), binascii.b2a_hex(data, sep="-", bytes_per_sep=-3), binascii.hexlify(bytearray(data), "x", 0))
print(failed(lambda: binascii.hexlify(b"ab", "::")), failed(lambda: binascii.hexlify(b"ab", "\xe9")), failed(lambda: binascii.hexlify(b"ab", "\u0100")), failed(lambda: binascii.hexlify(b"ab", 1)), failed(lambda: binascii.hexlify("ab")), failed(lambda: binascii.hexlify(b"ab", None)),  # type: ignore[arg-type,no-untyped-call]
      failed(lambda: binascii.hexlify(b"ab", ":", "1")), failed(lambda: binascii.hexlify(b"ab", bytearray(b":"))), failed(lambda: binascii.hexlify(b"ab", ":", 2**70)), binascii.hexlify(b"abc", ":", 3), binascii.hexlify(b"abc", ":", -4), binascii.hexlify(b"abcde", b"|", 2), binascii.hexlify(b"abcde", b"|", -2),  # type: ignore[arg-type,no-untyped-call]
      failed(lambda: binascii.hexlify(data=b"a", bytes_per_sep=2, sep=":")), failed(lambda: binascii.hexlify(b"a", data=b"b")), failed(lambda: binascii.hexlify(b"a", ":", 2, 3)), failed(lambda: binascii.hexlify()), failed(lambda: binascii.hexlify(b"a", sepp=":")))  # type: ignore[call-arg,misc,no-untyped-call]
for text in (b"", b"b901ef", b"B901EF", "b901ef", b"b9 01 ef", b"b901e", b"b901eg", b"xyz", bytearray(b"00ff")):  # type: ignore[assignment]
    print(text, failed(lambda: binascii.unhexlify(text)), failed(lambda: binascii.a2b_hex(text, ignorechars=b" ")), failed(lambda: binascii.unhexlify(text, ignorechars=b"xyz ")))  # type: ignore[no-untyped-call]
print(failed(lambda: binascii.unhexlify("b9\xe9")), failed(lambda: binascii.unhexlify(3)), failed(lambda: binascii.unhexlify(b"00", b" ")), failed(lambda: binascii.unhexlify(b"00", ignorechars=" ")))  # type: ignore[arg-type,call-arg,no-untyped-call]

# ---- crc32 ----
print(binascii.crc32(b""), binascii.crc32(b"hello"), binascii.crc32(b"hello", 0), binascii.crc32(b"world", binascii.crc32(b"hello ")) == binascii.crc32(b"hello world"), binascii.crc32(bytes(range(256))))
print(binascii.crc32(b"x", 2**32 - 1), binascii.crc32(b"x", 5), binascii.crc32(b"x", 2**31), binascii.crc32(bytearray(b"abc"), True), failed(lambda: binascii.crc32(b"x", 1.5)), failed(lambda: binascii.crc32("x")), failed(lambda: binascii.crc32(b"x", crc=1)))  # type: ignore[arg-type,call-arg,no-untyped-call]

# ---- base64, the module ----
print(base64.b64encode(b"foob"), base64.b64encode(b"\xfb\xff", altchars=b"-_"), base64.urlsafe_b64encode(b"\xfb\xff"), base64.standard_b64encode(b"a"), base64.b64encode(bytes(range(60)), wrapcol=76), base64.b64encode(bytearray(b"ab")), base64.b64encode(b"ab", padded=False))
print(base64.b64decode(b"Zm9vYg=="), base64.b64decode("Zm9vYg=="), base64.b64decode(b"Zm 9v"), failed(lambda: base64.b64decode(b"Zm 9v", validate=True)), base64.urlsafe_b64decode(b"-_8="), base64.b64decode(b"+_8=", altchars=b"+_"),  # type: ignore[no-untyped-call]
      base64.b64decode(b"Zm9v\nYmFy\n"), base64.b64decode(b"Zm9vYmFy", padded=False), base64.b64decode(b"Zm8", padded=False), failed(lambda: base64.b64decode(b"Zg=")), failed(lambda: base64.b64decode("Zm9v\xe9")), failed(lambda: base64.b64decode(b"Zm9v", altchars=b"abc")))  # type: ignore[no-untyped-call]
print(failed(lambda: base64.b16decode(b"B901EF")), failed(lambda: base64.b16encode(b"\xb9")), failed(lambda: base64.b16decode(b"b901ef")), failed(lambda: base64.b16decode(b"b901ef", casefold=True)))  # type: ignore[no-untyped-call]
