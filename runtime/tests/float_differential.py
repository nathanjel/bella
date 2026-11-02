#!/usr/bin/env python3
"""Differential test of libstdc++'s <charconv> against CPython's float formatting and parsing.

    python3 runtime/tests/float_differential.py --cxx g++ --std c++26 --cases 300000

Bella takes a float's digits from `std::to_chars` and reads decimal text with `std::from_chars`
(decision of 2026-11-02, licence entries L-06 and L-09); Python's own layer on top (repr's layout,
format types, round, the parser's spellings) is Bella's. This checks the digits:

* shortest: `std::to_chars(scientific)` gives the digits and exponent of `repr(x)`;
* `.Ne` and `.Nf` for N in 0..120: `std::to_chars` with a precision gives `format(x, ".Ne")`
  and `format(x, ".Nf")` character for character;
* parsing: `std::from_chars` gives `float(t)`'s bits, on repr round trips, long random decimals and
  exact midpoints between neighbouring doubles (with a hair either side), hundreds of digits long.

One difference is expected and is the wrapper's job: where the value is out of the double range,
`from_chars` reports `result_out_of_range` and Python returns an infinity or a zero. Any other
difference fails. Every GCC bump must pass this with --cases 3000000 (the size measured on
2026-11-02: no difference on GCC 16.2.0 against CPython 3.15.2).
"""
from __future__ import annotations

import argparse
import random
import struct
import subprocess
import sys
import tempfile
from decimal import Decimal, getcontext
from pathlib import Path

DRIVER = r"""
#include <charconv>
#include <cstdint>
#include <cstring>
#include <iostream>
#include <string>
// reads lines "kind precision hexbits-or-text", writes one result per line
int main() {
    std::ios::sync_with_stdio(false);
    std::string kind, a, b;
    static char buf[4096];
    while (std::cin >> kind >> a >> b) {
        if (kind == "parse") {
            double d = 0;
            auto r = std::from_chars(b.data(), b.data() + b.size(), d);
            std::uint64_t u;
            std::memcpy(&u, &d, 8);
            if (r.ec == std::errc::result_out_of_range) std::cout << "range\n";
            else if (r.ec != std::errc{} || r.ptr != b.data() + b.size()) std::cout << "invalid\n";
            else std::cout << u << '\n';
            continue;
        }
        std::uint64_t u = std::stoull(b, nullptr, 16);
        double d;
        std::memcpy(&d, &u, 8);
        std::to_chars_result r;
        if (kind == "short") r = std::to_chars(buf, buf + sizeof buf, d, std::chars_format::scientific);
        else if (kind == "e") r = std::to_chars(buf, buf + sizeof buf, d, std::chars_format::scientific, std::stoi(a));
        else r = std::to_chars(buf, buf + sizeof buf, d, std::chars_format::fixed, std::stoi(a));
        std::cout.write(buf, r.ptr - buf) << '\n';
    }
}
"""

HARD = [0.0, -0.0, 5e-324, 2.2250738585072014e-308, 2.225073858507201e-308, 1.7976931348623157e308,
        0.1, 0.3, 1 / 3, 2.0**53, 2.0**53 + 2, 1e16, 1e15, 1e-4, 1e-5, 123456789012345678.0, 5e-5, 1e23,
        9.5, 0.5, 2.5, 1.5e300, 4.35, 2.675]
OUT_OF_RANGE = ["1e400", "1e-400", "2.4703282292062327e-324", "2.4703282292062328e-324",
                "1.7976931348623158e308", "1.7976931348623159e308", "-1e400", "-1e-400",
                "4.9406564584124654e-324", "1e-325"]


def bits(x: float) -> int:
    return int(struct.unpack("<Q", struct.pack("<d", x))[0])


def from_bits(u: int) -> float:
    return float(struct.unpack("<d", struct.pack("<Q", u))[0])


def finite(rng: random.Random) -> float:
    while True:
        x = from_bits(rng.getrandbits(64))
        if x == x and abs(x) != float("inf"):
            return x


def digits_of_repr(x: float) -> str:
    """repr(x) as sign, significant digits and decimal exponent: '-15e16'."""
    s = repr(x)
    neg = s.startswith("-")
    s = s.lstrip("-")
    mant, _, exp = s.partition("e")
    ip, _, fp = mant.partition(".")
    allds = ip + fp
    stripped = allds.lstrip("0")
    if not stripped:
        return ("-" if neg else "") + "0"
    e = int(exp or "0") + len(ip) - 1 - (len(allds) - len(stripped))
    return f"{'-' if neg else ''}{stripped.rstrip('0') or '0'}e{e}"


def digits_of_chars(t: str) -> str:
    mant, _, exp = t.partition("e")
    neg = mant.startswith("-")
    ds = mant.lstrip("-").replace(".", "").rstrip("0") or "0"
    if ds == "0":
        return ("-" if neg else "") + "0"
    return f"{'-' if neg else ''}{ds}e{int(exp)}"


def cases(n: int, seed: int) -> list[tuple[str, str, str]]:
    """(line for the driver, kind, CPython's answer)."""
    rng = random.Random(seed)
    vals = HARD + [finite(rng) for _ in range(n)]
    vals += [from_bits(rng.getrandbits(52)) for _ in range(n // 8)]                 # subnormals
    vals += [float(rng.getrandbits(rng.randint(1, 64))) for _ in range(n // 8)]     # integers
    out: list[tuple[str, str, str]] = [(f"short 0 {bits(x):016x}", "short", digits_of_repr(x)) for x in vals]
    for x in vals[: n // 2]:
        p = rng.randint(0, 120)
        out.append((f"e {p} {bits(x):016x}", "e", format(x, f".{p}e")))
        p = rng.randint(0, 120)
        out.append((f"f {p} {bits(x):016x}", "f", format(x, f".{p}f")))
    texts = [repr(x) for x in vals[: n // 4]]
    texts += [f"{rng.randint(0, 10**20)}.{rng.randint(0, 10**20):020d}e{rng.randint(-330, 310)}" for _ in range(n // 4)]
    getcontext().prec = 1500
    for x in vals[: n // 12]:
        x = abs(x)
        y = from_bits(bits(x) + 1)
        if y == float("inf"):
            continue
        mid = format((Decimal(x) + Decimal(y)) / 2, "f")
        if "." not in mid:
            mid += "."
        texts += [mid, mid + "0000001", format(Decimal(mid) - Decimal(10) ** -1200, "f")]
    texts += OUT_OF_RANGE
    for t in texts:
        out.append((f"parse 0 {t}", "parse", str(bits(float(t)))))
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cxx", default="g++")
    ap.add_argument("--std", default="c++26")
    ap.add_argument("--cases", type=int, default=300_000)
    ap.add_argument("--seed", type=int, default=20261102)
    args = ap.parse_args()
    work = cases(args.cases, args.seed)
    with tempfile.TemporaryDirectory() as tmp:
        src, exe = Path(tmp) / "charconv.cpp", Path(tmp) / "charconv"
        src.write_text(DRIVER)
        subprocess.run([args.cxx, f"-std={args.std}", "-O2", str(src), "-o", str(exe)], check=True)
        got = subprocess.run([str(exe)], input="\n".join(c[0] for c in work) + "\n",
                             capture_output=True, text=True, check=True).stdout.splitlines()
    if len(got) != len(work):
        print(f"driver returned {len(got)} lines for {len(work)} cases", file=sys.stderr)
        return 1
    count: dict[str, int] = {}
    bad: dict[str, list[str]] = {}
    supplied = 0
    for (line, kind, want), have in zip(work, got, strict=True):
        count[kind] = count.get(kind, 0) + 1
        if kind == "short":
            have = digits_of_chars(have)
        if have == want:
            continue
        if kind == "parse" and have == "range":
            w = from_bits(int(want))
            if w == 0 or abs(w) == float("inf"):
                supplied += 1                  # out of range: the wrapper returns Python's ±inf or ±0
                continue
        bad.setdefault(kind, []).append(f"{line[:70]}: CPython {want[:40]!r}, libstdc++ {have[:40]!r}")
    for kind, n in count.items():
        print(f"{kind:6} {n:8} cases, {len(bad.get(kind, []))} differ from CPython {sys.version.split()[0]}")
    print(f"parse  {supplied:8} out of range, where the wrapper supplies Python's infinity or zero")
    for kind, lines in bad.items():
        for entry in lines[:5]:
            print("  DIFFERENT", kind, entry)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
