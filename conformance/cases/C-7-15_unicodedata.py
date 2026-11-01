# clause: C-7-15
# spec: section 7
# status: P1
# source: review log D-8 (2026-11-01): unicodedata is [P1], with CPython's Unicode tables
"""unicodedata with CPython 3.15.2's tables (Unicode 17.0.0): the four normalisation forms,
character properties, names in both directions, grapheme clusters, and the non-ASCII paths of
the phase-1 library that need it: a \\N{...} escape in a regex and a non-ASCII host in urlsplit."""
import re
import unicodedata
import urllib.parse

print("Unicode", unicodedata.unidata_version)
text = "Ångström ﬁ ① ½"
for form in ("NFC", "NFD", "NFKC", "NFKD"):
    out = unicodedata.normalize(form, text)
    print(form, ascii(out), len(out), unicodedata.is_normalized(form, text))
for ch in "aǺ①中‍\U0001f600":
    print(ascii(ch), unicodedata.category(ch), unicodedata.combining(ch), unicodedata.east_asian_width(ch),
          unicodedata.bidirectional(ch), unicodedata.mirrored(ch), unicodedata.decomposition(ch) or "-")
print(unicodedata.name("€"), ascii(unicodedata.lookup("GREEK SMALL LETTER ALPHA")), unicodedata.name("\x00", "no name"))
print(unicodedata.decimal("7"), unicodedata.digit("²"), unicodedata.numeric("½"), unicodedata.numeric("x", None))
try:
    unicodedata.lookup("NO SUCH CHARACTER NAME")
except KeyError as exc:
    print("unknown name:", type(exc).__name__)
print([ascii(str(g)) for g in unicodedata.iter_graphemes("é\U0001f44d\U0001f3fd\U0001f1f5\U0001f1f1a")])
print(bool(re.fullmatch(r"\N{EM DASH}+", "——")), re.sub(r"[\N{LATIN SMALL LETTER E WITH ACUTE}]", "e", "café"))
print(urllib.parse.urlsplit("http://bücher.example/path").hostname == "bücher.example")
try:
    urllib.parse.urlsplit("http://a℀b.example/")   # U+2100 becomes 'a/c' under NFKC
except ValueError as exc:
    print("netloc:", type(exc).__name__)
