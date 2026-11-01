#!/usr/bin/env python3
"""cli-easy: a command-line tool that slugifies lines of text (standard library only).

    slugs.py [--max-length N] [--separator SEP] [--no-lowercase] FILE

Reads lines, prints `original -> slug`, and a summary with the duplicated slugs. Transliteration
is NFKD decomposition plus the removal of combining marks, which is what python-slugify does
without its optional unidecode backend. Deterministic for a fixed input file.
"""
from __future__ import annotations

import argparse
import re
import sys
import unicodedata
from pathlib import Path

_NOT_ALLOWED = re.compile(r"[^-a-zA-Z0-9]+")
_DUPLICATE_SEP = re.compile(r"-{2,}")


def slugify(text: str, *, max_length: int = 0, separator: str = "-", lowercase: bool = True) -> str:
    decomposed = unicodedata.normalize("NFKD", text)
    ascii_text = "".join(ch for ch in decomposed if not unicodedata.combining(ch)).encode("ascii", "ignore").decode()
    if lowercase:
        ascii_text = ascii_text.lower()
    slug = _DUPLICATE_SEP.sub("-", _NOT_ALLOWED.sub("-", ascii_text)).strip("-")
    if max_length and len(slug) > max_length:
        words = slug.split("-")
        kept: list[str] = []
        for word in words:
            candidate = "-".join([*kept, word])
            if len(candidate) > max_length:
                break
            kept.append(word)
        slug = "-".join(kept) if kept else slug[:max_length]
    return slug.replace("-", separator) if separator != "-" else slug


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="slugify each line of FILE")
    parser.add_argument("file", type=Path)
    parser.add_argument("--max-length", type=int, default=0)
    parser.add_argument("--separator", default="-")
    parser.add_argument("--lowercase", action=argparse.BooleanOptionalAction, default=True)
    args = parser.parse_args(argv)

    lines = args.file.read_text(encoding="utf-8").splitlines()
    seen: dict[str, int] = {}
    for line in lines:
        if not line.strip():
            continue
        slug = slugify(line, max_length=args.max_length, separator=args.separator, lowercase=args.lowercase)
        seen[slug] = seen.get(slug, 0) + 1
        print(f"{line!r} -> {slug!r}")
    dupes = sorted(s for s, n in seen.items() if n > 1)
    print(f"{len(lines)} lines, {len(seen)} distinct slugs, {len(dupes)} duplicated: {dupes}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
