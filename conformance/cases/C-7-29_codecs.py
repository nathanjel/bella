# clause: C-7-29
# spec: section 7
# status: P1
# source: dialect specification section 7 (Text), Python/codecs.c, Modules/_codecsmodule.c, Objects/unicodeobject.c, Lib/codecs.py, Lib/encodings/__init__.py
"""The codec registry: the search that finds the phase-1 codecs by any of their names, what str.encode and bytes.decode take from it and what they
do without it, the incremental and stream classes over the built-in codecs, the error handlers as functions, and a codec a program registers."""
# ruff: noqa: ANN001, ANN002, ANN003, ANN201, ANN202, ANN204, B018, B023, E501, E731, PLR0133, SLF001
import codecs
import encodings
import encodings.aliases
import sys


def failed(f):  # type: ignore[no-untyped-def]
    try:
        f()
    except Exception as exc:
        return type(exc).__name__
    return "no error"


def notes(f):  # type: ignore[no-untyped-def]
    try:
        f()
    except Exception as exc:
        return type(exc).__name__, getattr(exc, "__notes__", None)
    return "no error"


print([name in sys.modules for name in ("_codecs", "codecs", "encodings", "encodings.aliases", "encodings.utf_8")])
for name in ("utf-8", "UTF8", "utf_8", "U8", "utf 8", "Utf-8", "latin-1", "L1", "iso-8859-1", "ISO_8859-1", "latin1", "ascii", "US-ASCII", "646", "us ascii", "utf-8-sig", "UTF_8_SIG"):
    info = codecs.lookup(name)
    print(name, info.name, type(info).__name__, isinstance(info, tuple), len(info), info._is_text_encoding, info is codecs.lookup(name), repr(info).split(" object ")[0])
print(failed(lambda: codecs.lookup("nope")), failed(lambda: codecs.lookup(1)), failed(lambda: codecs.lookup()), failed(lambda: codecs.lookup("a\0b")), failed(lambda: codecs.lookup("")))  # type: ignore[arg-type,call-arg,no-untyped-call]
print(encodings.normalize_encoding("UTF 8"), encodings.normalize_encoding("  utf--8.x "), encodings.aliases.aliases["u8"], encodings.aliases.aliases["l1"], encodings.aliases.aliases["646"], len(encodings.aliases.aliases) > 300)
print(failed(lambda: encodings.normalize_encoding(b"utf-8")), failed(lambda: encodings.normalize_encoding(1)))  # type: ignore[arg-type,no-untyped-call]

text = "aé€\U0001f600z"
for name in ("utf-8", "UTF8", "u8", "utf_8", "utf-8-sig", "latin-1", "l1", "iso8859-1", "ascii", "us-ascii", "646"):
    print(name, failed(lambda: text.encode(name)), text.encode(name, "replace"), text.encode(name, "ignore"), text.encode(name, "backslashreplace"), text.encode(name, "xmlcharrefreplace"), "aé".encode(name, "replace").decode(name, "replace"))  # type: ignore[no-untyped-call]
print(notes(lambda: "é".encode("ascii")), notes(lambda: "é".encode("646")), notes(lambda: "é".encode("us-ascii")), notes(lambda: "\udc80".encode("u8")), notes(lambda: "\udc80".encode("utf8")))  # type: ignore[no-untyped-call]
print(notes(lambda: b"\xff".decode("ascii")), notes(lambda: b"\xff".decode("646")), notes(lambda: b"\xff".decode("u8")), notes(lambda: b"\xff".decode("utf-8")), notes(lambda: b"\xff".decode("utf-8-sig")))  # type: ignore[no-untyped-call]
print(notes(lambda: codecs.encode("é", "ascii")), notes(lambda: codecs.decode(b"\xff", "utf-8")), notes(lambda: codecs.decode(b"\xff")), notes(lambda: codecs.encode("\udc80")))  # type: ignore[no-untyped-call]
print(b"".decode("nope"), failed(lambda: b"a".decode("nope")), failed(lambda: "".encode("nope")), failed(lambda: "a".encode("utf-8", "nope")), "a".encode("utf-8", "nope"), "a".encode("ascii", "nope"), b"a".decode("ascii", "nope"), failed(lambda: b"\xff".decode("ascii", "nope")), failed(lambda: "é".encode("ascii", "nope")))  # type: ignore[no-untyped-call]
print("﻿ab".encode("utf-8-sig"), b"\xef\xbb\xbfab".decode("utf-8-sig"), b"ab".decode("utf-8-sig"), b"\xef\xbb\xbf\xef\xbb\xbfab".decode("utf-8-sig") == "﻿ab", "ab".encode("utf-8-sig"))
print(b"a\x80\xffb".decode("utf-8", "surrogateescape").encode("utf-8", "surrogateescape"), b"\xed\xa0\x80".decode("utf-8", "surrogatepass").encode("utf-8", "surrogatepass"), b"a\xffb".decode("utf-8", "backslashreplace"), b"a\xffb".decode("ascii", "ignore"), failed(lambda: b"\xff".decode("utf-8", "xmlcharrefreplace")))  # type: ignore[no-untyped-call]
print(codecs.encode("aé"), codecs.encode("aé", "latin-1"), codecs.encode("aé", errors="replace", encoding="ascii"), codecs.decode(b"a\xc3\xa9"), codecs.decode(b"a\xe9", "l1"), codecs.decode(obj=b"\xff", encoding="ascii", errors="ignore"))
print(failed(lambda: codecs.encode()), failed(lambda: codecs.encode("a", 1)), failed(lambda: codecs.encode("a", "utf-8", 1)), failed(lambda: codecs.encode("a", "utf-8", "strict", 1)), failed(lambda: codecs.encode(1, "utf-8")), failed(lambda: codecs.decode("a", "utf-8")), failed(lambda: codecs.encode("a", "nope")), failed(lambda: codecs.encode("a", x=1)))  # type: ignore[call-overload,no-untyped-call]

print(codecs.utf_8_decode(b"a\xc3\xa9"), codecs.utf_8_decode(b"a\xc3"), codecs.utf_8_decode(b"a\xc3", "strict", False), failed(lambda: codecs.utf_8_decode(b"a\xc3", "strict", True)), codecs.utf_8_decode(b"a\xc3", "replace", True), codecs.utf_8_decode(b"\xe2\x82"), codecs.utf_8_decode(b"\xf0\x9f\x98"), codecs.utf_8_decode(b"\xed\xa0"), failed(lambda: codecs.utf_8_decode(b"\xed\xa0", None, True)), codecs.utf_8_decode(b""), codecs.utf_8_decode(bytearray(b"ab"), None))  # type: ignore[no-untyped-call]
print(codecs.utf_8_encode("aé"), codecs.utf_8_encode("aé", None), codecs.utf_8_encode("a\udc80", "surrogateescape"), codecs.latin_1_encode("aé"), codecs.latin_1_decode(b"a\xe9"), codecs.ascii_encode("ab"), codecs.ascii_decode(b"ab"), failed(lambda: codecs.ascii_encode("é")), codecs.ascii_encode("é", "replace"), codecs.ascii_decode(b"\xe9", "replace"), codecs.latin_1_encode("€", "xmlcharrefreplace"), codecs.readbuffer_encode(b"ab"), codecs.readbuffer_encode("aé"))  # type: ignore[no-untyped-call]
print(failed(lambda: codecs.utf_8_decode("a")), failed(lambda: codecs.utf_8_decode()), failed(lambda: codecs.utf_8_decode(b"a", 1)), failed(lambda: codecs.utf_8_decode(b"a", "strict", True, 1)), failed(lambda: codecs.utf_8_encode(b"a")), failed(lambda: codecs.utf_8_encode("a", errors="strict")), failed(lambda: codecs.latin_1_decode(1)), failed(lambda: codecs.ascii_encode("a", "a\0b")))  # type: ignore[arg-type,call-arg,no-untyped-call]
print(codecs.BOM_UTF8, codecs.BOM, codecs.BOM_LE, codecs.BOM_BE, codecs.BOM_UTF16 == codecs.BOM, codecs.BOM_UTF32_LE, codecs.BOM_UTF32_BE)

decoder = codecs.getincrementaldecoder("utf-8")()
print([decoder.decode(bytes([b])) for b in "aé€\U0001f600".encode()], decoder.getstate(), decoder.decode(b"\xe2"), decoder.getstate(), decoder.decode(b"\x82\xac", True), failed(lambda: decoder.decode(b"\xe2", True)))  # type: ignore[no-untyped-call]
decoder.reset()
print(decoder.decode(b"", True), type(decoder).__name__, type(decoder).__module__, [c.__name__ for c in type(decoder).__mro__], decoder.errors)
lenient = codecs.getincrementaldecoder("utf-8")("replace")
print(lenient.decode(b"a\xffb\xc3"), lenient.decode(b"", True), lenient.errors)
encoder = codecs.getincrementalencoder("utf-8")()
print(encoder.encode("aé"), encoder.encode("", True), encoder.getstate(), type(encoder).__name__)
sig_encoder = codecs.getincrementalencoder("utf-8-sig")()
print(sig_encoder.encode("a"), sig_encoder.encode("b"), sig_encoder.getstate())
sig_decoder = codecs.getincrementaldecoder("utf-8-sig")()
print([sig_decoder.decode(bytes([b])) for b in b"\xef\xbb\xbfab"], sig_decoder.decode(b"", True))
ascii_decoder = codecs.getincrementaldecoder("ascii")("ignore")
print(ascii_decoder.decode(b"a\xffb"), codecs.getincrementalencoder("latin-1")("replace").encode("a€"), codecs.getincrementaldecoder("latin-1")().decode(b"\xe9"))
print(list(codecs.iterencode(["a", "é", "€"], "utf-8")), list(codecs.iterdecode([b"a\xc3", b"\xa9", b"\xe2\x82", b"\xac"], "utf-8")), codecs.getencoder("utf-8")("é"), codecs.getdecoder("latin-1")(b"\xe9"))


class Sink:
    def __init__(self):  # type: ignore[no-untyped-def]
        self.parts = []

    def write(self, data):  # type: ignore[no-untyped-def]
        self.parts.append(data)


class Source:
    def __init__(self, data):  # type: ignore[no-untyped-def]
        self.data = data
        self.at = 0

    def read(self, size=-1):  # type: ignore[no-untyped-def]
        if size < 0:
            size = len(self.data) - self.at
        chunk = self.data[self.at:self.at + size]
        self.at += len(chunk)
        return chunk


sink = Sink()  # type: ignore[no-untyped-call]
writer = codecs.getwriter("utf-8")(sink)  # type: ignore[arg-type]
writer.write("aé")
writer.writelines(["€", "z"])
print(sink.parts, type(writer).__name__, writer.errors)
reader = codecs.getreader("utf-8")(Source("ligne é\nsecond €\nlast".encode()))  # type: ignore[arg-type,no-untyped-call]
print(repr(reader.readline()), repr(reader.read(3)), reader.readlines(), repr(reader.read()))
print([line for line in codecs.getreader("utf-8")(Source(b"a\nb\r\nc"))])  # type: ignore[arg-type,no-untyped-call]

for handler in (codecs.strict_errors, codecs.ignore_errors, codecs.replace_errors, codecs.xmlcharrefreplace_errors, codecs.backslashreplace_errors, codecs.namereplace_errors):
    print(handler.__name__, type(handler).__name__, handler is codecs.lookup_error(handler.__name__[:-7]))
enc_error = UnicodeEncodeError("ascii", "a€\U0001f600b", 1, 3, "why")
dec_error = UnicodeDecodeError("ascii", b"a\xff\xfeb", 1, 3, "why")
tr_error = UnicodeTranslateError("a€b", 1, 2, "why")
for handler in (codecs.ignore_errors, codecs.replace_errors, codecs.xmlcharrefreplace_errors, codecs.backslashreplace_errors, codecs.namereplace_errors,
                codecs.lookup_error("surrogateescape"), codecs.lookup_error("surrogatepass")):
    print([handler(e) if failed(lambda: handler(e)) == "no error" else failed(lambda: handler(e)) for e in (enc_error, dec_error, tr_error)], failed(lambda: handler(ValueError())), failed(lambda: handler(1)), failed(lambda: handler()))  # type: ignore[arg-type,call-arg,no-untyped-call]
print(failed(lambda: codecs.strict_errors(enc_error)), failed(lambda: codecs.strict_errors(KeyError("k"))), failed(lambda: codecs.strict_errors(1)))  # type: ignore[arg-type,no-untyped-call]
print(codecs.lookup_error("surrogateescape")(UnicodeDecodeError("utf-8", b"a\x80\xffb", 1, 3, "why")), codecs.lookup_error("surrogateescape")(UnicodeEncodeError("utf-8", "a\udc80\udcffb", 1, 3, "why")), codecs.lookup_error("surrogatepass")(UnicodeEncodeError("utf-8", "a\ud800b", 1, 2, "why")), codecs.lookup_error("surrogatepass")(UnicodeDecodeError("utf-8", b"a\xed\xa0\x80b", 1, 2, "why")))
odd = UnicodeEncodeError("ascii", "abc", -5, 99, "why")
print(codecs.replace_errors(odd), codecs.ignore_errors(odd), codecs.backslashreplace_errors(UnicodeEncodeError("ascii", "é", 5, 2, "why")), codecs.replace_errors(UnicodeEncodeError("ascii", "", 0, 1, "why")))
print(failed(lambda: codecs.lookup_error("nope")), failed(lambda: codecs.lookup_error(1)), failed(lambda: codecs.register_error("x", 1)), failed(lambda: codecs.register_error(1, len)), failed(lambda: codecs.register("x")), codecs.unregister(len))  # type: ignore[arg-type,func-returns-value,no-untyped-call]


def rot_encode(data, errors="strict"):  # type: ignore[no-untyped-def]
    return bytes((ord(c) + 1) % 256 for c in data), len(data)


def rot_decode(data, errors="strict"):  # type: ignore[no-untyped-def]
    return "".join(chr((b - 1) % 256) for b in bytes(data)), len(data)


searched = []  # type: ignore[var-annotated]


def search(name):  # type: ignore[no-untyped-def]
    searched.append(name)
    if name == "rot-one":
        return codecs.CodecInfo(rot_encode, rot_decode, name="rot-one")
    if name == "four":
        return (rot_encode, rot_decode, None, None)
    if name == "three":
        return (rot_encode, rot_decode, None)
    if name == "binary":
        return codecs.CodecInfo(rot_encode, rot_decode, name="binary", _is_text_encoding=False)
    return None


codecs.register(search)
print(codecs.lookup("ROT One").name, codecs.encode("abc", "rot-one"), "abc".encode("Rot One"), codecs.encode("abc", "four"), "abc".encode("four"), type(codecs.lookup("four")).__name__, searched)
print(failed(lambda: codecs.lookup("three")), failed(lambda: "a".encode("binary")), codecs.encode("a", "binary"), failed(lambda: codecs.lookup("unknown-one")), searched)  # type: ignore[no-untyped-call]
codecs.lookup("rot-one")
print(searched.count("rot-one"), codecs.unregister(search), failed(lambda: codecs.lookup("rot-one")), searched.count("rot-one"))  # type: ignore[func-returns-value,no-untyped-call]
