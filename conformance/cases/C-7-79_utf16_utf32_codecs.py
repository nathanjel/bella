# clause: C-7-79
# spec: section 7
# status: P1
# source: dialect specification section 7, Text: codecs' phase-1 codecs include UTF-16 and UTF-32 (C-7-07 stopped there)
"""UTF-16 and UTF-32 both ways: the byte order mark written for the native form and read to choose
the order, the -le and -be forms, surrogate pairs, the error each malformed input raises (its
class, the encoding it names and the range it covers) and what every built-in handler makes of
it, lone surrogates in a string, the stateful decoders (what a final call leaves and what a
non-final one keeps for later), the byte order the ex decoders report, and the incremental and
stream codecs the encodings package builds over them."""
import codecs
import io
from collections.abc import Callable
from functools import partial

HANDLERS = ("strict", "ignore", "replace", "backslashreplace", "surrogatepass", "surrogateescape")


def shown(result: object) -> str:
    if isinstance(result, bytes):
        return result.hex(" ")
    if isinstance(result, str):
        return ascii(result)
    if isinstance(result, tuple):
        return "(" + ", ".join(shown(item) for item in result) + ")"
    return repr(result)


def attempt(thunk: Callable[[], object]) -> str:
    try:
        result = thunk()
    except (UnicodeEncodeError, UnicodeDecodeError) as exc:
        return f"{type(exc).__name__}({exc.encoding}, {exc.start}, {exc.end})"
    except Exception as exc:  # noqa: BLE001  # which exception, by class
        return type(exc).__name__
    return shown(result)


def encoded(text: str, codec: str, handler: str) -> str:
    return attempt(lambda: text.encode(codec, handler))


def decoded(data: bytes, codec: str, handler: str) -> str:
    return attempt(lambda: data.decode(codec, handler))




TEXTS = ("", "a", "é€", "\U0001f600x", "a\ud800b", "\udc80", "\ud83d\ude00", "\ud83d")
for codec in ("utf-16", "utf-16-le", "utf-16-be", "utf-32", "utf-32-le", "utf-32-be"):
    for text in TEXTS:
        print(codec, ascii(text), *(encoded(text, codec, handler) for handler in HANDLERS))

DATA = (b"", b"a", b"a\x00", b"\xff\xfea\x00", b"\xfe\xff\x00a", b"\x00\xd8", b"\x00\xd8a\x00", b"\x00\xdc", b"=\xd8\x00\xde",
        b"=\xd8", b"=\xd8a", b"a\x00b", b"\xff\xfe", b"\x00\xd8\x00\xd8\x00\xdc", b"\x80\xdc", b"\xff\xfe\x00\x00a\x00\x00\x00",
        b"\x00\x00\xfe\xffa\x00\x00\x00", b"a\x00\x00\x00", b"\x00\xd8\x00\x00", b"\x00\x00\x11\x00", b"\xff\xff\xff\xff", b"a\x00\x00",
        b"\x80\x00\x11\x80a\x00\x00\x00")
for codec in ("utf-16", "utf-16-le", "utf-16-be", "utf-32", "utf-32-le", "utf-32-be"):
    for data in DATA:
        print(codec, data.hex(" "), *(decoded(data, codec, handler) for handler in HANDLERS))

for name, function in (("utf_16_decode", codecs.utf_16_decode), ("utf_16_le_decode", codecs.utf_16_le_decode),
                       ("utf_32_decode", codecs.utf_32_decode), ("utf_32_be_decode", codecs.utf_32_be_decode)):
    for data in (b"\xff\xfe", b"\xff\xfea", b"a\x00=\xd8", b"a\x00=\xd8\x00", b"a\x00\x00", b"\x00\x00\xfe\xff\x00\x00"):
        print(name, data.hex(" "), attempt(partial(function, data)), attempt(partial(function, data, None, True)))
for data in (b"", b"\xff", b"\xff\xfe", b"\xfe\xffa", b"\xfe\xff\x00a", b"\x00a"):
    for order in (0, -1, 1, 5):
        print("utf_16_ex_decode", data.hex(" "), order, attempt(partial(codecs.utf_16_ex_decode, data, None, order)),
              attempt(partial(codecs.utf_16_ex_decode, data, None, order, True)))
for data in (b"", b"\xff\xfe\x00\x00", b"\x00\x00\xfe\xff\x00\x00\x00a", b"a\x00"):
    for order in (0, -1, 1):
        print("utf_32_ex_decode", data.hex(" "), order, attempt(partial(codecs.utf_32_ex_decode, data, None, order, True)))
for order in (0, -1, 1, -3, 2):
    print("encode byteorder", order, attempt(partial(codecs.utf_16_encode, "a\U0001f600", None, order)),
          attempt(partial(codecs.utf_32_encode, "a\ud800", "surrogatepass", order)), attempt(partial(codecs.utf_32_encode, "a\ud800", None, order)))
print("lengths", attempt(partial(codecs.utf_16_le_encode, "é\U0001f600")), attempt(partial(codecs.utf_32_be_encode, "é")))

for codec in ("utf-16", "utf-32", "utf-16-be"):
    encoder = codecs.getincrementalencoder(codec)()
    pieces = [encoder.encode("ab"), encoder.encode("\U0001f600"), encoder.encode("", final=True)]
    encoder.reset()
    pieces.append(encoder.encode("c"))
    whole = "ab\U0001f600".encode(codec)
    decoder = codecs.getincrementaldecoder(codec)()
    parts = [decoder.decode(whole[i:i + 1]) for i in range(len(whole))]
    print(codec, [piece.hex() for piece in pieces], [ascii(part) for part in parts], ascii(decoder.decode(b"", final=True)),
          attempt(partial(codecs.getincrementaldecoder(codec)().decode, whole[:-1], True)))
    stream = io.BytesIO()
    writer = codecs.getwriter(codec)(stream)
    writer.write("x")
    writer.write("y")
    reader = codecs.getreader(codec)(io.BytesIO(stream.getvalue()))
    print(codec, stream.getvalue().hex(), ascii(reader.read()))
