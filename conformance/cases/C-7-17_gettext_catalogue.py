# clause: C-7-17
# spec: section 7
# status: P1
# source: decision S-4 (2026-11-01, docs/staging.md): a catalogue without plural forms is [P1]
"""A GNU catalogue without Plural-Forms in its header: gettext uses its default plural rule,
compiles nothing, and phase 1 loads it (the boundary of C-7-16, decision S-4)."""
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


header = "Content-Type: text/plain; charset=UTF-8\n"
translations = gettext.GNUTranslations(io.BytesIO(catalogue({"": header, "apple\0apples": "jabłko\0jabłka", "pear": "gruszka"})))
print(translations.gettext("pear"), translations.gettext("plum"), translations.info())
for n in (1, 2, 5, 22, 25):
    print(n, translations.ngettext("apple", "apples", n))
