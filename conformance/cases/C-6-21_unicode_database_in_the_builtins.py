# clause: C-6-21
# spec: section 6 (int, float, complex, str and its formatting, the codecs' error handlers), section 3 (__slots__)
# status: P1
# source: Objects/unicodeobject.c (_PyUnicode_TransformDecimalAndSpaceToASCII, PyUnicode_IsIdentifier), Objects/longobject.c
#         (PyLong_FromUnicodeObject), Objects/floatobject.c, Objects/complexobject.c, Objects/unicode_formatter.c and
#         Objects/stringlib/unicode_format.h (get_integer), Objects/unicode_format.c (the % format's errors), Python/codecs.c
#         (PyCodec_NameReplaceErrors), Objects/typeobject.c (valid_identifier)
"""What the builtins ask the Unicode database: int(), float() and complex() of a str read every Unicode decimal digit as its
ASCII digit and every Unicode space as a space, stopping at the first character that is neither (DEL among them, once the
string is not ASCII); a format specification's width and precision and a format field's index are Unicode decimal digits; a
% format's unknown character is shown whether it is printable or not; the namereplace error handler writes each character's
name (its alias where the character is a code point the database keeps aliases at) and a hex escape where it has none, from
every encoder and called by hand; a __slots__ name is an identifier by XID_Start and XID_Continue."""
import codecs
from collections.abc import Callable


def attempt(thunk: Callable[[], object]) -> str:
    try:
        result = thunk()
    except Exception as exc:  # noqa: BLE001  # which exception, by class
        return type(exc).__name__
    return ascii(result)


def call(function: object, *args: object) -> str:
    try:
        result = function(*args)  # type: ignore[operator]
    except Exception as exc:  # noqa: BLE001  # which exception, by class
        return type(exc).__name__
    return ascii(result)


NUMBERS = ("٣٤", "\u2003 12 \u3000", "１２３", "\U0001d7ce\U0001d7cf", "٣_٤", "1\x7f٣", "٣\x7f", "½", "٣½", "-٣", "\u205f+٤\u2028",
           "", "\u3000", "٣ ٤", "०", "꯰꯱", "\U000104a0\U000104a1", "٣١", "1e٢")
for text in NUMBERS:
    print("number", ascii(text), call(int, text), call(float, text), call(complex, text))
print("int base", attempt(lambda: int("٣٤", 8)), attempt(lambda: int("٠x١٠", 0)), attempt(lambda: int("٠x١٠", 16)), attempt(lambda: int("٠٧", 0)),
      attempt(lambda: int("٠٠", 0)), attempt(lambda: int("z٣", 36)), attempt(lambda: int("٣", 2)))
print("float forms", attempt(lambda: float("٣.٥")), attempt(lambda: float("١e٣")), attempt(lambda: float("\u3000inf")),
      attempt(lambda: float("٣.")), attempt(lambda: float(".٥")), attempt(lambda: float("٣_٥.٥")))
print("complex forms", attempt(lambda: complex("٣+٤j")), attempt(lambda: complex("(٣-٤j)")), attempt(lambda: complex("\u3000٤j\u3000")),
      attempt(lambda: complex("٤J")), attempt(lambda: complex("٣_٤+١j")))

def formatted(template: str, *args: object, **kwds: object) -> str:
    try:
        return ascii(template.format(*args, **kwds))
    except Exception as exc:  # noqa: BLE001  # which exception, by class
        return type(exc).__name__


def percent(template: str, value: object) -> str:
    try:
        return ascii(template % value)
    except Exception as exc:  # noqa: BLE001  # which exception, by class
        return type(exc).__name__


print("format", ascii(format(5, "٣")), ascii(format(5.25, ".١f")), ascii(format(5, "٠٣")), formatted("{:٤}", "ab"),
      ascii(format(3.5, "١٠.٢e")), ascii(format(7, "é>٤")), attempt(lambda: format(5, "٣x٤")), attempt(lambda: format(1, "½")))
print("fields", formatted("{٠}{١}", "a", "b"), formatted("{٠[١]}", "xyz"), formatted("{x٠}", **{"x٠": 1}), formatted("{½}", 1),
      formatted("{٠!r}", "q"), formatted("{٠:{١}}", 1, 3), formatted("{٠٠}", "z"))
print("percent", *(percent(template, 1) for template in ("%é", "%\u0378", "%\U0001f600", "%\x7f", "%\u2028", "%٣d", "%\u3000")))

TEXT = "aé€\U0001f600\u0378\ud800\U000f0000\U000f0200가一\x80"
for encoding in ("ascii", "latin-1", "utf-8", "utf-16-le", "utf-32-be"):
    print("namereplace", encoding, call(TEXT.encode, encoding, "namereplace"))
print("handler", attempt(lambda: codecs.namereplace_errors(UnicodeEncodeError("ascii", "x\xe9€y", 1, 3, "why"))),
      attempt(lambda: codecs.namereplace_errors(UnicodeEncodeError("ascii", "\U000f01e0\U0001f600", 0, 2, "why"))),
      attempt(lambda: codecs.namereplace_errors(UnicodeDecodeError("utf-8", b"\xff", 0, 1, "why"))),
      call(codecs.namereplace_errors, ValueError("x")), attempt(lambda: b"\xff".decode("utf-8", "namereplace")),
      attempt(lambda: b"\xff".decode("ascii", "namereplace")), codecs.lookup_error("namereplace") is codecs.namereplace_errors)


def slotted(names: tuple[str, ...]) -> str:
    try:
        cls = type("K", (), {"__slots__": names})
    except Exception as exc:  # noqa: BLE001  # which exception, by class
        return type(exc).__name__
    obj = cls()
    for index, name in enumerate(names):
        setattr(obj, name if not name.startswith("__") else "_K" + name, index)
    return ascii(sorted(n for n in vars(cls) if not n.startswith("__") or n == "__slots__")) + " " + ascii(
        [getattr(obj, n if not n.startswith("__") else "_K" + n) for n in names])


for names in (("é", "名前"), ("a\u0300", "·x"), ("_é",), ("__é",), ("\u0300a",), ("1é",), ("é-",), ("\U0001d400",), ("ℌ",), ("é", "\xe9")):
    print("slots", ascii(names), slotted(names))
