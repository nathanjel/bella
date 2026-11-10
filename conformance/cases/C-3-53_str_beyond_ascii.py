# clause: C-3-53
# spec: section 3
# status: P1
# source: Objects/unicodeobject.c (the str predicates and case conversions), Objects/unicodectype.c (the Unicode database)
"""str's predicates and case conversions beyond ASCII, as CPython's Unicode database has them: each predicate of characters
from many scripts and categories (letters with and without case, a titlecase digraph, digits and numerals that are not
decimal, the spaces and line breaks, marks, symbols, controls, unassigned and private code points, a lone surrogate), the
empty str, and strings mixing them; upper, lower, casefold, title, swapcase and capitalize with the mappings that grow
(ß, ligatures, İ), the titlecase digraphs, and the final sigma, which looks past case-ignorable characters on both sides;
strip, split and splitlines with the whitespace and line breaks beyond ASCII."""

CHARS = ("a", "Z", "é", "ß", "ǅ", "ǆ", "Ǆ", "Σ", "ς", "ﬁ", "İ", "ı", "ŉ", "ᾳ", "ᾼ", "Ⅻ", "ⅻ", "ⓐ", "Ⓐ", "ª", "º", "ʰ",
         "٣", "३", "²", "½", "௰", "〇", "一", "Ⅰ", " ", " ", "　", " ", "​", " ", " ", "\x85",
         "\x1c", "\x1f", "́", "ͅ", "­", "'", "’", ":", "·", "€", "😀", "", "\U000e0001", "͸",
         "\ud800", "\U0001d7d8", "\U00010341", "ᏸ", "Ꭰ", "ꭰ", "Ⴀ", "ⴀ", "Ა")
PREDICATES = ("isalpha", "isalnum", "isdecimal", "isdigit", "isnumeric", "isspace", "islower", "isupper", "istitle",
              "isprintable", "isidentifier")
for ch in CHARS:
    flags = "".join("1" if getattr(ch, p)() else "." for p in PREDICATES)
    print(hex(ord(ch)), flags, [hex(ord(c)) for c in ch.upper()], [hex(ord(c)) for c in ch.lower()],
          [hex(ord(c)) for c in ch.casefold()], [hex(ord(c)) for c in ch.title()], [hex(ord(c)) for c in ch.swapcase()])

for s in ("", "Straße", "ΣΑΣ", "ΣΑΣ ΑΣ", "Σ", "aΣ", "aΣb", "aΣ́", "áΣ", "a'Σ'", "ﬁnal ǆungla", "ǆUNGLA ǅungla",
          "İstanbul", "hello World", "ΌΣΟΣ ΑΣ.", "ᾳ ᾼ", "a1 b2", "٣٤٥", "½", "Ⅻ", "x²", "  　", "a b",
          "MiXeD Ǆ ǅ ǆ", "o'neil Mc'Donald", "ⓐⓑ", "Ⓐⓑ", "a​b"):
    print(repr(s), [getattr(s, p)() for p in PREDICATES])
    print("  ", s.upper(), s.lower(), s.casefold(), s.title(), s.swapcase(), s.capitalize())

text = "　 a b c  d\x1c"
print(text.split(), text.strip(), text.lstrip(), text.rstrip(), "x\x85y z w\x1cv\x1dt\x1eu".splitlines(),
      "x\x85y z".splitlines(keepends=True), "​x​".strip(), len("İ".lower()), "ﬃ".upper(), "ŉ".upper())
