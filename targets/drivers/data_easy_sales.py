#!/usr/bin/env python3
"""data-easy: a data script over CSV with the standard library only.

    sales.py SALES.csv

Aggregates a sales file by region and month, computes exact money with Decimal and
Fraction-based shares, and prints a fixed-width report with humanized sizes (humanize, MIT).
"""
from __future__ import annotations

import csv
import sys
from collections import defaultdict
from datetime import date
from decimal import ROUND_HALF_EVEN, Decimal
from fractions import Fraction
from pathlib import Path
from statistics import mean, median

import humanize


def main(path: str) -> int:
    rows = list(csv.DictReader(Path(path).open(encoding="utf-8", newline="")))
    by_region: dict[str, Decimal] = defaultdict(Decimal)
    by_month: dict[tuple[int, int], Decimal] = defaultdict(Decimal)
    amounts: list[Decimal] = []
    for row in rows:
        amount = Decimal(row["amount"]).quantize(Decimal("0.01"), rounding=ROUND_HALF_EVEN)
        d = date.fromisoformat(row["date"])
        by_region[row["region"]] += amount
        by_month[(d.year, d.month)] += amount
        amounts.append(amount)
    total = sum(amounts, Decimal(0))
    print(f"{len(rows)} rows, total {total:,.2f}, mean {mean(amounts):.2f}, median {median(amounts):.2f}")
    for region, amount in sorted(by_region.items(), key=lambda kv: (-kv[1], kv[0])):
        share = Fraction(amount) / Fraction(total)
        print(f"{region:<10} {amount:>12,.2f}  {float(share):6.1%}  ({share.limit_denominator(100)})")
    for (year, month), amount in sorted(by_month.items()):
        print(f"{year}-{month:02d} {amount:>12,.2f}  {humanize.intword(int(amount))}")
    print("largest sale:", humanize.intcomma(max(amounts)), "file size:",  # type: ignore[arg-type]  # a Decimal: humanize accepts any number at runtime
          humanize.naturalsize(Path(path).stat().st_size, binary=True))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
