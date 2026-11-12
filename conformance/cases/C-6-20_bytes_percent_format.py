# clause: C-6-20
# spec: section 6 (bytes, bytearray)
# status: P1
# source: PEP 461; Objects/bytesobject.c (CPython 3.15.2: _PyBytes_FormatEx, format_obj, formatlong, formatfloat, byte_converter)
"""bytes % args and bytearray % args: every conversion bytes takes (%c, %b and %s by the buffer or __bytes__, %a and %r by
ascii(), the integers with their flags, width and precision, the floats), * from the arguments, mappings and keys, what
is left over, what each refuses (the exception's class only), and what the result is: a bytes, or a bytearray for a
bytearray on the left, never a subclass."""
# ruff: noqa: UP031


class Raw:
    def __bytes__(self) -> bytes:
        return b"<raw>"


class Number:
    def __index__(self) -> int:
        return 7


class Sub(bytes):
    pass


def refused(f: object) -> str:
    try:
        f()  # type: ignore[operator]
    except Exception as e:
        return type(e).__name__
    return "accepted"


print(b"%d %i %u" % (1, -2, 3), b"%x %X %o %#x %#o %#X" % (255, 255, 8, 255, 8, 255))
print(b"%5d|%-5d|%05d|%+d|% d|%.3d|%+.2d" % (42, 42, 42, 42, 42, 7, 7))
print(b"%f %.2f %e %.3E %g %G %10.4f|%-10.2e|" % (1.5, 2.345, 12345.678, 0.000123, 1e20, 1e-5, 3.14159, 2.5))
print(b"%c%c%c" % (65, b"B", bytearray(b"C")), b"%5c|%-3c|" % (b"x", b"y"))  # type: ignore[str-format]
print(b"%s %b %s" % (b"bytes", bytearray(b"array"), Raw()), b"%.3s|%5b|%-5s|" % (b"abcdef", b"ab", b"cd"))  # type: ignore[str-format]
print(b"%a %r %a" % ("text", "naïve", 1.5), b"%.4a|" % ("abcdefg",))
print(b"%(x)d-%(y)s" % {b"x": 1, b"y": b"two"}, b"%*d|%-*d|%.*f" % (5, 1, 4, 2, 2, 3.14159))
print(b"%d" % Number(), b"%x" % Number(), b"%%", b"100%%" % ())  # type: ignore[str-format]
print(b"%d" % True, b"%s" % b"", refused(lambda: b"%-3%|" % ()), refused(lambda: b"%-3%|" % (1,)))  # type: ignore[str-format]
print(type(b"%d" % 1).__name__, type(bytearray(b"%d") % 1).__name__, bytearray(b"%s-%s") % (b"a", b"b"), type(Sub(b"%d") % 1).__name__)
print("refused:", refused(lambda: b"%s" % "str"), refused(lambda: b"%d" % "1"), refused(lambda: b"%c" % 256), refused(lambda: b"%c" % b"ab"),  # type: ignore[str-format]
      refused(lambda: b"%d %d" % (1,)), refused(lambda: b"%d" % (1, 2)), refused(lambda: b"%z" % 1), refused(lambda: b"%(x)d" % (1,)),  # type: ignore[str-format]
      refused(lambda: b"%(x)d" % {}), refused(lambda: b"%" % ()), refused(lambda: b"%x" % 1.5), refused(lambda: b"%f" % "x"),  # type: ignore[str-format]
      refused(lambda: b"%s" % 1), refused(lambda: b"%*d" % ("x", 1)), refused(lambda: b"%(x" % {}), refused(lambda: b"%c" % -1))  # type: ignore[str-format]
print("left over:", b"abc" % {}, b"abc" % [], refused(lambda: b"abc" % 1), refused(lambda: b"abc" % ()), refused(lambda: b"%s" % ()))  # type: ignore[str-format]
