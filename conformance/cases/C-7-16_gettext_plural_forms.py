# clause: C-7-16
# spec: section 7
# status: P2+
# expect: Plural-Forms
# source: decision S-4 (2026-11-01, docs/staging.md): plural forms from a catalogue stay [P2+]
"""A GNU catalogue whose header has Plural-Forms: gettext compiles the header's expression with
exec (gettext.c2py) while it loads the catalogue, so phase 1 refuses with the milestone's name.
C-7-17 is the same catalogue without the header, which phase 1 loads."""
import gettext
import io
import struct


def catalogue(entries: dict[str, str]) -> bytes:
    """A .mo file: the header, the tables of original and translated strings, the strings."""
    keys = sorted(entries)
    originals = [k.encode() for k in keys]
    translations = [entries[k].encode() for k in keys]
    count = len(keys)
    originals_at, translations_at = 28, 28 + 8 * count
    offset = translations_at + 8 * count
    tables: list[bytes] = []
    data = b""
    for strings in (originals, translations):
        for s in strings:
            tables.append(struct.pack("<2I", len(s), offset + len(data)))
            data += s + b"\0"
    return struct.pack("<7I", 0x950412DE, 0, count, originals_at, translations_at, 0, 0) + b"".join(tables) + data


header = "Content-Type: text/plain; charset=UTF-8\nPlural-Forms: nplurals=3; plural=(n==1 ? 0 : n%10>=2 && n%10<=4 && (n%100<10 || n%100>=20) ? 1 : 2);\n"
translations = gettext.GNUTranslations(io.BytesIO(catalogue({"": header, "apple\0apples": "jabłko\0jabłka\0jabłek"})))
for n in (1, 2, 5, 22, 25):
    print(n, translations.ngettext("apple", "apples", n))
