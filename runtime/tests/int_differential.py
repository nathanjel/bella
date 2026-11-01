#!/usr/bin/env python3
"""Differential test of runtime/include/bella/int.hpp against CPython's int.

    python3 runtime/tests/int_differential.py --cxx g++ --std c++26 --cases 2000

Generates operand pairs (random plus every edge of the 63-bit immediate range), computes the
expected results in Python, builds a small C++ driver, and compares. A result outside the
immediate range is expected to be reported as "promote" by the runtime until BigInt exists
(the driver prints that word when NotImplemented is thrown). Review round two checked 1,156
such cases on the corrected floor/mod paths; this keeps the check in CI.
"""
from __future__ import annotations

import argparse
import random
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
KMIN, KMAX = -(2**62), 2**62 - 1
OPS = ["add", "sub", "mul", "floordiv", "mod", "lshift", "rshift", "and", "or", "xor", "pow"]

DRIVER = r"""
#include "bella/int.hpp"
#include <iostream>
#include <string>
using bella::Int;
static void emit(Int (*f)(Int, Int), Int a, Int b) {
    try { std::cout << bella::to_string(f(a, b)) << '\n'; }
    catch (const bella::NotImplemented&) { std::cout << "promote\n"; }
    catch (const bella::ZeroDivisionError&) { std::cout << "zerodiv\n"; }
    catch (const bella::ValueError&) { std::cout << "valueerror\n"; }
}
int main() {
    std::string op; long long a, b;
    while (std::cin >> op >> a >> b) {
        Int x = Int::from_small(a), y = Int::from_small(b);
        if (op == "add") emit(bella::int_add, x, y);
        else if (op == "sub") emit(bella::int_sub, x, y);
        else if (op == "mul") emit(bella::int_mul, x, y);
        else if (op == "floordiv") emit(bella::int_floordiv, x, y);
        else if (op == "mod") emit(bella::int_mod, x, y);
        else if (op == "lshift") emit(bella::int_lshift, x, y);
        else if (op == "rshift") emit(bella::int_rshift, x, y);
        else if (op == "and") emit(bella::int_and, x, y);
        else if (op == "or") emit(bella::int_or, x, y);
        else if (op == "xor") emit(bella::int_xor, x, y);
        else if (op == "pow") emit(bella::int_pow, x, y);
    }
}
"""


def expected(op: str, a: int, b: int) -> str:
    try:
        if op == "add":
            r = a + b
        elif op == "sub":
            r = a - b
        elif op == "mul":
            r = a * b
        elif op == "floordiv":
            r = a // b
        elif op == "mod":
            r = a % b
        elif op == "lshift":
            try:
                r = a << b
            except ValueError:          # CPython decides, not a re-implementation of its rule
                return "valueerror"
        elif op == "rshift":
            try:
                r = a >> b
            except ValueError:          # CPython decides, not a re-implementation of its rule
                return "valueerror"
        elif op == "and":
            r = a & b
        elif op == "or":
            r = a | b
        elif op == "xor":
            r = a ^ b
        elif op == "pow":
            if b < 0:
                return "promote"  # the runtime reports float results as not implemented
            if b > 200:
                return "promote"
            r = a**b
        else:
            raise ValueError(op)
    except ZeroDivisionError:
        return "zerodiv"
    return str(r) if KMIN <= r <= KMAX else "promote"


def operands(rng: random.Random, n: int) -> list[tuple[str, int, int]]:
    edges = [KMIN, KMIN + 1, -1, 0, 1, KMAX - 1, KMAX, 2**31, -(2**31), 2**32, 3, -3, 7, -7]
    cases: list[tuple[str, int, int]] = []
    for op in OPS:
        for a in edges:
            for b in edges:
                if op in ("lshift", "rshift", "pow"):
                    continue
                cases.append((op, a, b))
    for a in edges:
        for s in (0, 1, 2, 31, 61, 62, 63, 64, 70):
            cases.append(("lshift", a, s))
            cases.append(("rshift", a, s))
        for e in (0, 1, 2, 3, 10, 31, 62, 63, 64):
            cases.append(("pow", a, e))
    while len(cases) < n:
        op = rng.choice(OPS)
        if op in ("lshift", "rshift"):
            cases.append((op, rng.randint(KMIN, KMAX), rng.randint(0, 70)))
        elif op == "pow":
            cases.append((op, rng.randint(-1000, 1000), rng.randint(0, 40)))
        else:
            mag = rng.choice([2**8, 2**31, 2**40, 2**61, 2**62])
            cases.append((op, rng.randint(-mag, mag - 1), rng.randint(-mag, mag - 1)))
    return cases


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--cxx", default="g++")
    ap.add_argument("--std", default="c++26")
    ap.add_argument("--cases", type=int, default=2000)
    ap.add_argument("--seed", type=int, default=1)
    args = ap.parse_args(argv)
    cases = operands(random.Random(args.seed), args.cases)
    with tempfile.TemporaryDirectory() as tmp:
        src = Path(tmp) / "driver.cpp"
        src.write_text(DRIVER, encoding="utf-8")
        exe = Path(tmp) / "driver"
        cmd = [args.cxx, f"-std={args.std}", "-O1", "-fsanitize=undefined", "-fno-sanitize-recover=all",
               "-I", str(ROOT / "include"), str(src), "-o", str(exe)]
        build = subprocess.run(cmd, capture_output=True, text=True, check=False)
        if build.returncode != 0:
            print(build.stderr, file=sys.stderr)
            print(f"int-test: build failed with {args.cxx} -std={args.std}", file=sys.stderr)
            return 2
        feed = "".join(f"{op} {a} {b}\n" for op, a, b in cases)
        run = subprocess.run([str(exe)], input=feed, capture_output=True, text=True, check=False)
        if run.returncode != 0:
            print(run.stderr, file=sys.stderr)
            print("int-test: driver crashed (UBSan reports above)", file=sys.stderr)
            return 1
    got = run.stdout.splitlines()
    failures = 0
    for (op, a, b), g in zip(cases, got, strict=True):
        e = expected(op, a, b)
        if e != g:
            failures += 1
            if failures <= 20:
                print(f"MISMATCH {op}({a}, {b}): expected {e}, got {g}")
    promoted = sum(1 for (op, a, b) in cases if expected(op, a, b) == "promote")
    print(f"int-test: {len(cases)} cases, {len(cases) - promoted} exact, {promoted} promotions reported, "
          f"{failures} mismatches ({args.cxx} -std={args.std})")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
