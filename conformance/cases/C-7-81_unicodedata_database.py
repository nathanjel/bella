# clause: C-7-81
# spec: section 7
# status: P1
# source: review log D-8 (2026-11-01): unicodedata is [P1] with CPython's tables; C-7-15 has its main paths
"""unicodedata's whole database, beside C-7-15: every property of a character in both databases (Unicode 17.0.0 and the
3.2.0 one normalisation's stringprep users read), the properties 3.15 added (block, the grapheme cluster break, the Indic
conjunct break, Extended_Pictographic, the identifier predicates), the algorithmic names both ways, the aliases and named
sequences lookup finds and name never gives, what lookup reads a name from (str as UTF-8, bytes, nothing else bytes-like), the
four forms on the cases the composition rules turn on (Hangul, reordering, exclusions, singletons, the 3.2.0 corrections) with
whether an already normalised string comes back itself, a str subclass read as stored and answered with a str, the grapheme
clusters of TR29's hard cases over a slice, the Segment objects, the types' descriptors, the capsule, the docs, and the class
of every error."""
import types
import unicodedata
from collections.abc import Iterable
from typing import Literal

UCD = unicodedata.ucd_3_2_0
FORMS: tuple[Literal["NFC", "NFD", "NFKC", "NFKD"], ...] = ("NFC", "NFD", "NFKC", "NFKD")


def call(function: object, *args: object) -> str:
    try:
        result = function(*args)  # type: ignore[operator]
    except Exception as exc:  # noqa: BLE001  # which exception, by class
        return type(exc).__name__
    return ascii(result)


def bounds(segment: object) -> tuple[int, int]:
    return segment.start, segment.end  # type: ignore[attr-defined]  # typeshed has iter_graphemes yield str


def spans(segments: Iterable[object]) -> list[tuple[int, int, str]]:
    return [(*bounds(s), ascii(str(s))) for s in segments]


print("versions", unicodedata.unidata_version, UCD.unidata_version, type(UCD).__module__, type(UCD).__qualname__)
print("names", sorted(n for n in dir(unicodedata) if not n.startswith("__")))
print("UCD", sorted(n for n in dir(unicodedata.UCD) if not n.startswith("_")))
print("kinds", type(unicodedata.name).__name__, type(unicodedata.UCD.name).__name__, type(UCD.name).__name__)

PROPERTIES = ("category", "bidirectional", "combining", "east_asian_width", "mirrored", "decomposition")
DEFAULTED = ("decimal", "digit", "numeric", "name")
MODULE_ONLY = ("block", "grapheme_cluster_break", "indic_conjunct_break", "extended_pictographic", "isxidstart", "isxidcontinue")
CHARS = ("\x00", "\t", " ", "A", "a", "7", "\xb2", "\xbd", "\xc5", "ȡ", "́", "א", "ا", "٣", "क", "्",
         "ก", "ᄀ", "ᅡ", "ᆨ", "‍", "₩", "Ⅰ", "①", "　", "あ", "一", "가",
         "豈", "ﬁ", "️", "Ａ", "\U0001d7ce", "\U0001f1f5", "\U0001f44d", "\U0001f3fd", "\U0001f600", "\U00017000",
         "\U00018b00", "\U0001b170", "\U0002a700", "\U00031350", "\U000e0001", "\U000f0000", "\U0010fffd", "\U0001fbf0", " ")
for ch in CHARS:
    print(ascii(ch), *(call(getattr(db, n), ch) for db in (unicodedata, UCD) for n in PROPERTIES),
          *(call(getattr(db, n), ch, None) for db in (unicodedata, UCD) for n in DEFAULTED),
          *(call(getattr(unicodedata, n), ch) for n in MODULE_ONLY))

NAMES = ("HANGUL SYLLABLE GA", "HANGUL SYLLABLE GAG", "HANGUL SYLLABLE HIH", "hangul syllable ga", "CJK UNIFIED IDEOGRAPH-4E00",
         "CJK UNIFIED IDEOGRAPH-9FFF", "CJK UNIFIED IDEOGRAPH-31350", "CJK UNIFIED IDEOGRAPH-4e00", "CJK UNIFIED IDEOGRAPH-3400",
         "CJK UNIFIED IDEOGRAPH-0041", "TANGUT IDEOGRAPH-17000", "KHITAN SMALL SCRIPT CHARACTER-18B00", "NUSHU CHARACTER-1B170",
         "CJK COMPATIBILITY IDEOGRAPH-F900", "LATIN CAPITAL LETTER GHA", "LATIN CAPITAL LETTER A WITH MACRON AND GRAVE",
         "KEYCAP NUMBER SIGN", "BYTE ORDER MARK", "NULL", "LINE FEED", "latin small letter a", "LATIN SMALL LETTER  A",
         "EURO SIGN", "NO SUCH NAME", "", "A" * 300, "HANGUL SYLLABLE", "HANGUL SYLLABLE GAX", "TANGUT IDEOGRAPH-18800",
         "CJK UNIFIED IDEOGRAPH-04E00", "CJK UNIFIED IDEOGRAPH-110000", "CJK UNIFIED IDEOGRAPH-4E00 ", "HANGUL SYLLABLE GAGG")
for name in NAMES:
    print("lookup", ascii(name[:40]), call(unicodedata.lookup, name), call(UCD.lookup, name), call(unicodedata.lookup, name.encode()))
LOOKUPS: tuple[object, ...] = (b"NULL", b"latin small letter a", bytearray(b"NULL"), "\ud800", "NULL\x00",
                               "LATIN SMALL LETTER A\x00", "HANGUL SYLLABLE GA\x00", b"\xff\xfe", "A" * 257, "A" * 256, "\xe9", 1, None)
for arg in LOOKUPS:
    label = ascii(arg)[:24] if isinstance(arg, (str, bytes)) else type(arg).__name__
    print("lookup argument", label, call(unicodedata.lookup, arg), call(UCD.lookup, arg))
for ch in ("가", "힣", "一", "\U00031350", "\U00017000", "豈", "Ƣ", "﻿", "\U000e0100", "\U00010000", "\U000f0000", "\U000f0200"):
    print("name", ascii(ch), call(unicodedata.name, ch), call(UCD.name, ch))

TEXTS = ("abc", "\xc5ngstr\xf6m", "Å", "Å", "각", "각", "ậ", "ậ",
         "क़", "ﬁ", "①\xbd", "ẛ̣", "̈́", "\U0001d15e", "Ω", "ཱི", "é́", "Ą̊",
         "ᄀ가", "Ａ　", "À̖", "x́ͅ", "⫝̸", "ୋ", "",
         "a" + "̖́" * 15, "ᄀ" * 3 + "ᅡ" * 3 + "ᆨ" * 3, "\U000110a5\U000110ba", "ᄒퟀ")
for text in TEXTS:
    for db_normalize, db_is_normalized in ((unicodedata.normalize, unicodedata.is_normalized), (UCD.normalize, UCD.is_normalized)):
        print(ascii(text), *(call(db_normalize, form, text) + "/" + call(db_is_normalized, form, text) for form in FORMS))
same = "already plain"
accented = "\xe9"
print("itself", [unicodedata.normalize(form, same) is same for form in FORMS], [UCD.normalize(form, same) is same for form in FORMS],
      [unicodedata.normalize(form, accented) is accented for form in FORMS])
# each answer is a new str, but for the empty one and one Latin-1 character, which are one object each
print("a new str", unicodedata.category("a") is unicodedata.category("a"), unicodedata.east_asian_width("a") is unicodedata.east_asian_width("b"),
      unicodedata.block("a") is unicodedata.block("a"), unicodedata.grapheme_cluster_break("a") is unicodedata.grapheme_cluster_break("a"),
      unicodedata.indic_conjunct_break("a") is unicodedata.indic_conjunct_break("a"), unicodedata.name("a") is unicodedata.name("a"),
      unicodedata.decomposition("\xe9") is unicodedata.decomposition("\xe9"), "| one object:", unicodedata.bidirectional("a") is unicodedata.bidirectional("b"),
      unicodedata.east_asian_width("\u3042") is unicodedata.east_asian_width("\u3044"), unicodedata.decomposition("a") is unicodedata.decomposition("b"))


class Sub(str):
    def __len__(self) -> int:
        return 5

    def __getitem__(self, index: object) -> str:  # never read by the module
        return "z"

    def __str__(self) -> str:
        return "zz"


sub = Sub("abc")
print("subclass", *(type(db_normalize(form, sub)).__name__ + (" itself" if db_normalize(form, sub) is sub else "")
                    for db_normalize in (unicodedata.normalize, UCD.normalize) for form in FORMS),
      type(unicodedata.normalize("NFC", Sub(""))).__name__, unicodedata.is_normalized("NFC", sub), unicodedata.is_normalized("NFD", Sub("\xe9")),
      [(type(str(s)).__name__, str(s)) for s in unicodedata.iter_graphemes(Sub("ab"))], call(unicodedata.category, Sub("ab")),
      unicodedata.category(Sub("a")), unicodedata.name(Sub("a")))

CLUSTERS = ("éx", "\r\n\n\r", "\U0001f1f5\U0001f1f1\U0001f1e6", "\U0001f468‍\U0001f469‍\U0001f467", "\U0001f44d\U0001f3fd!",
            "각각", "क्षि", "क्‍ष", "a‍b", "؀a",
            "\U0001f3f3️‍\U0001f308", "\x00́", "", "กำ", "\U0001f600‍‍\U0001f600", "ᄀᄀ각ᆨᆨ", "\ŕ", "a\U0001f1f5\U0001f1f1\U0001f1e6\U0001f1e8")
for text in CLUSTERS:
    print("graphemes", ascii(text), spans(unicodedata.iter_graphemes(text)))
seq = "ab́c\U0001f1f5\U0001f1f1d"
for start, end in ((1, 4), (2, 3), (-3, -1), (0, 100), (5, 2), (-100, 2), (3, 3), (5, 6)):
    print("slice", start, end, spans(unicodedata.iter_graphemes(seq, start, end)))
iterator = unicodedata.iter_graphemes("ab")
segment = next(iterator)
print("segment", repr(segment), str(segment), bounds(segment), type(segment).__name__, type(iterator).__name__,
      iter(iterator) is iterator, call(next, iterator), call(next, iterator), call(next, iterator),
      call(setattr, segment, "start", 1), call(type(segment)), call(type(iterator)))

print("errors", call(unicodedata.name, ""), call(unicodedata.name, "ab"), call(unicodedata.name, 1), call(unicodedata.name),
      call(unicodedata.lookup, 1), call(unicodedata.normalize, "NFX", "a"), call(unicodedata.normalize, "NFC", 1),
      call(unicodedata.normalize, 1, "a"), call(unicodedata.is_normalized, "nfc", "a"), call(unicodedata.normalize, "NFX", ""),
      call(unicodedata.is_normalized, "NFX", ""), call(unicodedata.UCD), call(unicodedata.iter_graphemes, 1),
      call(unicodedata.iter_graphemes, "a", "b"), call(unicodedata.iter_graphemes, "a", 2**70), call(unicodedata.numeric, "a"),
      call(unicodedata.decimal, "a"), call(unicodedata.digit, "a"), call(unicodedata.name, "\U000f0000"),
      call(unicodedata.category, "a", "b"), call(unicodedata.category), call(unicodedata.block, 1), call(getattr, UCD, "block"),
      call(unicodedata.UCD.name, "a"), call(unicodedata.UCD.name, UCD, "a"), call(unicodedata.UCD.name, unicodedata, "a"),
      call(unicodedata.UCD.name), call(unicodedata.mirrored, b"a"), call(unicodedata.decimal, "a", 1, 2), call(UCD.decimal),
      call(unicodedata.lookup), call(unicodedata.lookup, "a", "b"), call(UCD.category, "ab"))
print("defaults", unicodedata.decimal("x", "d"), unicodedata.digit("x", 1.5), unicodedata.numeric("x", None), unicodedata.name("\x00", 0),
      UCD.decimal("\U0001d7ce", "d"), UCD.numeric("↉", "n"), UCD.name("ȡ", "none"))

capsule = vars(unicodedata)["_ucnhash_CAPI"]
print("capsule", type(capsule).__name__, type(capsule) is types.CapsuleType, type(capsule).__module__)
SegmentType, IteratorType = type(segment), type(iterator)
for cls in (unicodedata.UCD, SegmentType, IteratorType):
    print("type", cls.__module__, cls.__qualname__, cls.__name__, repr(cls.__doc__),
          [(n, type(cls.__dict__[n]).__name__) for n in sorted(cls.__dict__) if not n.startswith("_")])
print("members", repr(vars(unicodedata.UCD)["unidata_version"].__doc__), vars(SegmentType)["start"].__doc__, vars(SegmentType)["end"].__doc__,
      call(setattr, UCD, "unidata_version", "x"), call(setattr, UCD, "other", 1), call(setattr, segment, "x", 1),
      call(delattr, segment, "end"))
print("reprs", repr(unicodedata.name), repr(unicodedata.UCD.name), repr(vars(unicodedata.UCD)["unidata_version"]), repr(unicodedata.UCD))
print("doc", repr(unicodedata.__doc__))
for name in sorted(n for n in dir(unicodedata) if not n.startswith("_")):
    value = getattr(unicodedata, name)
    if callable(value) and not isinstance(value, type):
        print(name, type(value).__name__, value.__name__, value.__qualname__, value.__module__, repr(value.__doc__))
for name in sorted(n for n in dir(unicodedata.UCD) if not n.startswith("_") and n != "unidata_version"):
    method, bound = getattr(unicodedata.UCD, name), getattr(UCD, name)
    print("UCD", name, type(method).__name__, method.__qualname__, method.__doc__ == getattr(unicodedata, name).__doc__, type(bound).__name__,
          bound.__qualname__, bound.__module__, bound.__self__ is UCD)
