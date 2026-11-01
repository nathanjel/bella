#!/usr/bin/env python3
"""cli-tricky: a pycodestyle-like style checker over a tokenizer (pycodestyle, MIT).

    check.py [--select E1,W2] [--max-line-length N] FILE...

Runs pycodestyle's checker (its own copy, vendored) over the given files and prints the report
in its standard format plus a per-code summary. Tricky because pycodestyle registers checks by
introspecting functions (inspect.signature), stores options in a namespace it mutates through
__dict__, and drives everything through generators over tokenize output.
"""
from __future__ import annotations

import sys
from collections import Counter

import pycodestyle


def main(argv: list[str]) -> int:
    style = pycodestyle.StyleGuide(paths=argv, quiet=False, max_line_length=88, select=None, ignore=["W6"])  # type: ignore[no-untyped-call]  # pycodestyle is untyped
    report = style.check_files()  # type: ignore[no-untyped-call]  # as above
    counts = Counter(report.counters)
    for code in sorted(c for c in counts if c[:1] in "EW"):
        print(f"{code}: {counts[code]}")
    print(f"total: {report.total_errors}")
    return 1 if report.total_errors else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
