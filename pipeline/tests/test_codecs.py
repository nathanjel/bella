"""_codecs and the registry, compiled, against CPython: the messages case C-7-29 does not compare, what the start-up imports, a codec
the program registers, and what stops by name."""
from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path

from pipeline.build import build
from pipeline.tests.test_review_2026_11_03 import same

MESSAGES = r"""
import codecs
import _codecs
def show(f):
    try:
        print(repr(f()))
    except BaseException as e:
        print(type(e).__name__, e, getattr(e, "__notes__", None))
for f in (lambda: codecs.lookup(1), lambda: codecs.lookup(), lambda: codecs.lookup("a", "b"), lambda: codecs.lookup(encoding="a"), lambda: codecs.lookup("a\0b"),
          lambda: codecs.lookup(""), lambda: codecs.lookup("\udc80"), lambda: codecs.register("x"), lambda: codecs.register(), lambda: codecs.unregister(1),
          lambda: codecs.encode(), lambda: codecs.encode("a", 1), lambda: codecs.encode("a", "utf-8", 1), lambda: codecs.encode("a", "utf-8", "strict", 1),
          lambda: codecs.encode("a", x=1), lambda: codecs.encode("a", "a\0b"), lambda: codecs.encode(1, "utf-8"), lambda: codecs.decode("a", "utf-8"),
          lambda: codecs.encode("a", "nope"), lambda: codecs.encode("a", "utf-8", "a\0b"), lambda: codecs.decode(b"\xff", "ascii"), lambda: codecs.decode(b"\xff"),
          lambda: codecs.utf_8_decode(), lambda: codecs.utf_8_decode("a"), lambda: codecs.utf_8_decode(b"a", 1), lambda: codecs.utf_8_decode(b"a", "strict", True, 1),
          lambda: codecs.utf_8_decode(1), lambda: codecs.utf_8_decode(b"a", errors="strict"), lambda: codecs.utf_8_decode(b"\xc3", None, []),
          lambda: codecs.utf_8_encode(b"a"), lambda: codecs.utf_8_encode("a", errors="strict"), lambda: codecs.utf_8_encode(), lambda: codecs.utf_8_encode("a", None, 1),
          lambda: codecs.ascii_encode("a", "a\0b"), lambda: codecs.ascii_encode("a", 1), lambda: codecs.latin_1_decode(1), lambda: codecs.readbuffer_encode("aé"),
          lambda: codecs.readbuffer_encode(1), lambda: codecs.readbuffer_encode(bytearray(b"a")), lambda: codecs.register_error("x", 1), lambda: codecs.register_error(1, len),
          lambda: codecs.register_error(), lambda: codecs.register_error("x"), lambda: codecs.lookup_error(1), lambda: codecs.lookup_error("nope"), lambda: codecs.lookup_error(),
          lambda: _codecs._unregister_error("strict"), lambda: _codecs._unregister_error("nope"), lambda: _codecs._unregister_error(1),
          lambda: codecs.replace_errors(ValueError()), lambda: codecs.replace_errors(), lambda: codecs.replace_errors(1), lambda: codecs.replace_errors(exc=1),
          lambda: codecs.strict_errors(1), lambda: codecs.strict_errors(KeyError("k")), lambda: codecs.xmlcharrefreplace_errors(UnicodeDecodeError("a", b"a", 0, 1, "r")),
          lambda: _codecs._normalize_encoding(1), lambda: _codecs._normalize_encoding(), lambda: _codecs._normalize_encoding(encoding="A b"), lambda: _codecs._normalize_encoding("ab\0cd"),
          lambda: _codecs._normalize_encoding("\udc80"), lambda: _codecs._normalize_encoding("a", "b"), lambda: "é".encode("646"), lambda: b"\xff".decode("u8"),
          lambda: "a".encode("a\0b"), lambda: b"a".decode("utf-8", "a\0b"), lambda: str(b"a", "a\0b"), lambda: bytes("a", "utf-8", "a\0b"), lambda: "é".encode("utf-8", "nope"),
          lambda: "é".encode("ascii", "nope"), lambda: b"\xff".decode("ascii", "nope"), lambda: b"\xff".decode("latin-1", "nope"), lambda: "\udc80".encode("latin-1", "nope"),
          lambda: codecs.replace_errors(UnicodeEncodeError.__new__(UnicodeEncodeError)), lambda: codecs.ignore_errors(UnicodeDecodeError.__new__(UnicodeDecodeError)),
          lambda: codecs.lookup_error("surrogatepass")(UnicodeEncodeError("ascii", "\ud800", 0, 1, "r")), lambda: codecs.lookup_error("surrogateescape")(UnicodeEncodeError("ascii", "a", 0, 1, "r")),
          lambda: codecs.lookup_error("surrogatepass")(UnicodeDecodeError("utf-8", b"a", 0, 1, "r")), lambda: codecs.lookup_error("surrogateescape")(UnicodeDecodeError("utf-8", b"a", 0, 1, "r"))):
    show(f)
for name in ("strict", "ignore", "replace", "xmlcharrefreplace", "backslashreplace", "namereplace", "surrogatepass", "surrogateescape"):
    h = codecs.lookup_error(name)
    print(name, h, h.__name__, h.__qualname__, h.__module__, h.__self__, type(h).__name__, h.__doc__)
for name in ("register", "lookup", "encode", "utf_8_decode", "_normalize_encoding"):
    f = getattr(_codecs, name)
    print(name, f, f.__module__, f.__self__ is _codecs, f.__qualname__, f.__doc__ is None or f.__doc__[:20])
print(_codecs.__name__, _codecs.__doc__, _codecs.__spec__.origin, _codecs.__loader__.__name__, hasattr(_codecs, "__all__"), sorted(n for n in dir(_codecs) if not n.startswith("__")))
e2 = UnicodeEncodeError("a", "abc", 0, 1, "r"); e2.object = b"xyz"
e3 = UnicodeDecodeError("a", b"abc", 0, 1, "r"); e3.object = "xyz"
e5 = UnicodeEncodeError("ascii", "abc", 0, 1, "r"); e5.encoding = 3
class E(UnicodeEncodeError):
    @property
    def start(self):
        return 2
    @property
    def object(self):
        return "zzzzzz"
for f in (lambda: codecs.replace_errors(e2), lambda: codecs.replace_errors(e3), lambda: codecs.ignore_errors(e3), lambda: codecs.lookup_error("surrogatepass")(e5),
          lambda: codecs.replace_errors(E("a", "abc", 0, 2, "r")), lambda: codecs.backslashreplace_errors(E("a", "a\xe9c", 1, 2, "r"))):
    show(f)
"""

STARTUP = r"""
import sys
print([n for n in sorted(sys.modules) if n == "_codecs" or n == "codecs" or n.startswith("encodings")], type(sys.modules["codecs"]).__name__, sys.modules["encodings"].__name__, sys.modules["encodings.utf_8"].__spec__.name)
print("é".encode("U8"), b"\xe9".decode("L1"), "é".encode("utf-8-sig"), "\udc80".encode("utf-8", "surrogateescape"), b"".decode("nope"), b"".decode("cp1252"))
import codecs
print(codecs.lookup("utf-8").name, codecs.lookup("latin1").name, "encodings.latin_1" in sys.modules, "encodings.utf_8_sig" in sys.modules)
print(sorted(n for n in sys.modules if n.startswith("encodings")))
"""

REGISTERED = r"""
import codecs
def rot_encode(data, errors="strict"):
    return bytes((ord(c) + 1) % 256 for c in data), len(data)
def rot_decode(data, errors="strict"):
    return "".join(chr((b - 1) % 256) for b in bytes(data)), len(data)
def search(name):
    if name == "rot-one":
        return codecs.CodecInfo(rot_encode, rot_decode, name="rot-one")
    if name == "lying":
        return (lambda s, errors="strict": ("not bytes", 1), rot_decode, None, None)
    if name == "wrong":
        return (lambda s, errors="strict": "no tuple", rot_decode, None, None)
    if name == "failing":
        return (lambda s, errors="strict": 1 / 0, rot_decode, None, None)
    return None
codecs.register(search)
def show(f):
    try:
        print(repr(f()))
    except BaseException as e:
        print(type(e).__name__, e, getattr(e, "__notes__", None))
for f in (lambda: "abc".encode("rot-one"), lambda: "abc".encode("ROT One"), lambda: codecs.encode("abc", "rot-one"), lambda: codecs.decode(b"bcd", "rot-one"),
          lambda: "abc".encode("lying"), lambda: "abc".encode("wrong"), lambda: "abc".encode("failing"), lambda: codecs.encode("abc", "wrong"), lambda: codecs.encode("abc", "failing"),
          lambda: bytes("abc", "rot-one"), lambda: bytes("abc", "lying"), lambda: "".encode("rot-one"), lambda: codecs.lookup("rot-one") is codecs.lookup("ROT-ONE")):
    show(f)
"""


def test_messages() -> None:
    same(MESSAGES)


def test_what_the_start_up_imports() -> None:
    same(STARTUP)


def test_a_codec_the_program_registers() -> None:
    same(REGISTERED)


def test_what_is_absent_stops_by_name() -> None:
    cases = (("import codecs\ncodecs.utf_7_encode('a')", "utf_7_encode"), ("import codecs\ncodecs.unicode_escape_decode(b'a')", "unicode_escape_decode"),
             ("import codecs\ncodecs.escape_decode(b'a')", "escape_decode"), ("import codecs\nprint('é'.encode('ascii', 'namereplace'))", "namereplace"),
             ("import codecs\ncodecs.register_error('strict', print)", "strict"),
             ("import codecs\ncodecs.register_error('mine', lambda e: ('', e.end))\nprint('é'.encode('ascii', 'mine'))", "mine"),
             ("import codecs\ncodecs.register(lambda n: codecs.CodecInfo(None, lambda b, errors='strict': ('x', 1), name=n) if n == 'mine' else None)\nprint(b'a'.decode('mine'))", "memoryview"))
    for body, name in cases:
        with tempfile.TemporaryDirectory() as tmp:
            prog = Path(tmp, "prog.py")
            prog.write_text(f"print('start')\n{body}\n", encoding="utf-8")
            got = subprocess.run([str(build(prog, "prog.py"))], capture_output=True, text=True, check=False)
        assert (got.returncode, got.stdout) == (70, "start\n") and "not implemented" in got.stderr and name in got.stderr, (body, got)


if __name__ == "__main__":
    test_messages()
    test_what_the_start_up_imports()
    test_a_codec_the_program_registers()
    test_what_is_absent_stops_by_name()
