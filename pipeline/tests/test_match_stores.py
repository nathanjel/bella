"""The order in which a `match` case's captures are stored (pipeline/l1/captures.py) against CPython's own code.

The port has two halves, the code generator's (what stands before the stores) and the optimizer's (which stores it
exchanges). Both are checked at once, against what the reference interpreter compiles: for a pattern, the names in the
order of the STORE instructions `dis` shows are the order `store_order` must give. The patterns are generated, a fixed
seed, every kind of pattern nested in every other, written on one line or over several (the optimizer exchanges nothing
across a line), as the last case or not, guarded or not, and with the names as fast locals, with one of them a global or
a cell, and at module level (where no store is a STORE_FAST and the order is the order of capture).

The shapes measured by hand on 2026-11-22 (TODO.md, with objects that say when they go) are rows of their own, so that
the expectation does not rest on `dis` alone.

Run under pytest or directly: python3 -m pipeline.tests.test_match_stores
"""
from __future__ import annotations

import ast
import dis
import random
import sys
from types import CodeType

from pipeline.l1.captures import capture_plan, store_order

SEED = 20261122
PATTERNS = 1500

MEASURED = {
    "[a, b]": "a b",
    "[a, b, c]": "a b c",
    "[a, b, c, d]": "a b c d",
    "[a, *b]": "a b",
    "[a, [b, c]]": "b c a",
    "[a, [b, c], d]": "b c d a",
    "[a, b, [c]]": "c a b",
    '{"x": a, "y": b}': "a b",
    '{"x": a, **b}': "b a",
    '{"x": a, "y": b, **c}': "c a b",
    "C(a, b)": "a b",
    "C(x=a, y=b)": "a b",
    "[a, b] as c": "a b c",
    "[a, b] | [b, a]": "a b",
}


class Maker:
    """Patterns that bind exactly the names they are given."""

    def __init__(self, rng: random.Random, lines: bool) -> None:
        self.rng = rng
        self.lines = lines

    def join(self, items: list[str]) -> str:
        out = ""
        for i, item in enumerate(items):
            if i:
                out += ",\n" if self.lines and self.rng.random() < 0.4 else ", "
            out += item
        return out

    def split(self, names: list[str], parts: int) -> list[list[str]]:
        groups: list[list[str]] = [[] for _ in range(parts)]
        for name in names:
            groups[self.rng.randrange(parts)].append(name)
        return groups

    def leaf(self) -> str:
        return self.rng.choice(["_", "0", '"k"', "None", "K.v", "[]", "{}", "C()", "[*_]", "[_, *_]"])

    def pattern(self, names: list[str], depth: int, refutable: bool = False) -> str:
        rng = self.rng
        if not names and (depth <= 0 or rng.random() < 0.6):
            return self.leaf() if not refutable else rng.choice(["0", "None", "[]", "{}", "C()"])
        if len(names) == 1 and not refutable and (depth <= 0 or rng.random() < 0.5):
            return names[0]
        kinds = ["sequence", "sequence", "mapping", "class"]
        if not refutable and names:
            kinds.append("as")
        if depth > 0 and len(names) >= 1:
            kinds.append("or")
        kind = rng.choice(kinds)
        if kind == "as":
            inner = self.pattern(names[:-1], depth - 1)
            if inner in ("_",):                               # `_ as n` is written `n`
                inner = "0"
            gap = "\n" if self.lines and rng.random() < 0.3 else " "
            return f"({inner}{gap}as {names[-1]})"
        if kind == "or":
            alternatives = []
            for _ in range(rng.choice([2, 2, 3])):
                mixed = names[:]
                rng.shuffle(mixed)
                alternatives.append(self.pattern(mixed, depth - 1, refutable=True))
            gap = "\n" if self.lines and rng.random() < 0.3 else " "
            return "(" + f"{gap}| ".join(alternatives) + ")"
        if kind == "sequence":
            rest = names[:]
            star: str | None = None
            roll = rng.random()
            if roll < 0.2 and rest:
                star = "*" + rest.pop(rng.randrange(len(rest)))
            elif roll < 0.35:
                star = "*_"
            count = rng.randrange(0 if star or not rest else 1, 4)
            items = [self.pattern(group, depth - 1) for group in self.split(rest, count)] if count else []
            if not count and rest:
                items = [self.pattern(rest, depth - 1)]
            if star is not None:
                items.insert(rng.randrange(len(items) + 1), star)
            return "[" + self.join(items) + "]"
        if kind == "mapping":
            rest = names[:]
            double = "**" + rest.pop(rng.randrange(len(rest))) if rest and rng.random() < 0.3 else None
            count = rng.randrange(0 if not rest else 1, 4)
            groups = self.split(rest, count) if count else []
            items = [f'"k{i}": {self.pattern(group, depth - 1)}' for i, group in enumerate(groups)]
            if double is not None:
                items.append(double)
            return "{" + self.join(items) + "}"
        count = rng.randrange(0 if not names else 1, 4)
        groups = self.split(names, count) if count else []
        keyword_from = rng.randrange(count + 1)
        items = [(f"x{i}=" if i >= keyword_from else "") + self.pattern(group, depth - 1) for i, group in enumerate(groups)]
        return "C(" + self.join(items) + ")"


def program(pattern: str, scope: str, last: bool, guard: bool, special: str) -> str:
    """One case in a function (or at module level), `special` being the name that is a global or a cell."""
    indent = "    " if scope != "module" else ""
    lines = []
    if scope != "module":
        lines.append("def f(s):")
        if scope == "global":
            lines.append(f"    global {special}")
    lines.append(f"{indent}match s:")
    lines.append(f"{indent}    case {pattern}" + (" if g" if guard else "") + ":")
    lines.append(f"{indent}        pass")
    if not last:
        lines += [f"{indent}    case 0:", f"{indent}        pass"]
    if scope == "cell":
        lines.append(f"    return lambda: {special}")
    return "\n".join(lines) + "\n"


def cpython_stores(code: CodeType, names: list[str]) -> list[str]:
    out: list[str] = []
    for instr in dis.get_instructions(code):
        if instr.opname in ("STORE_FAST", "STORE_GLOBAL", "STORE_NAME", "STORE_DEREF"):
            out.append(instr.argval)
        elif instr.opname == "STORE_FAST_STORE_FAST":
            out += list(instr.argval)
        elif instr.opname == "STORE_FAST_LOAD_FAST":
            out.append(instr.argval[0])
    return [n for n in out if n in names]


def both_orders(source: str, scope: str, special: str) -> tuple[list[str], list[str], list[str]]:
    """(the order of capture, the port's order of the stores, CPython's) for the one case of `source`."""
    tree = ast.parse(source)
    match = next(n for n in ast.walk(tree) if isinstance(n, ast.Match))
    names, plan = capture_plan(match.cases[0].pattern)
    fast = [scope != "module" and not (scope in ("global", "cell") and n == special) for n in names]
    ours = [names[i] for i in store_order(plan, fast)]
    code = compile(source, "<pattern>", "exec")
    if scope != "module":
        code = next(c for c in code.co_consts if isinstance(c, CodeType) and c.co_name == "f")
    return names, ours, cpython_stores(code, names)


def test_the_shapes_measured_by_hand() -> None:
    for pattern, expected in MEASURED.items():
        source = program(pattern, "fast", last=False, guard=False, special="")
        _, ours, theirs = both_orders(source, "fast", "")
        assert ours == expected.split(), (pattern, ours)
        assert theirs == expected.split(), (pattern, theirs)


def test_generated_patterns_store_in_cpythons_order() -> None:
    assert sys.version_info[:2] == (3, 15), "the reference interpreter's code is what the port is compared with"
    rng = random.Random(SEED)
    compared = refused = moved = 0
    for _ in range(PATTERNS):
        names = [f"n{i}" for i in range(rng.randrange(2, 7))]
        rng.shuffle(names)
        pattern = Maker(rng, lines=rng.random() < 0.5).pattern(names, depth=3, refutable=True)
        special = rng.choice(names)
        last, guard = rng.random() < 0.5, rng.random() < 0.3
        for scope in ("fast", "global", "cell", "module"):
            source = program(pattern, scope, last, guard, special)
            try:
                captured, ours, theirs = both_orders(source, scope, special)
            except SyntaxError:
                refused += 1                                  # an alternative that makes the next unreachable, and the like
                continue
            assert sorted(theirs) == sorted(names), (source, theirs)
            assert ours == theirs, (source, ours, theirs)
            compared += 1
            moved += ours != captured
    assert compared > PATTERNS * 3 and refused < compared // 10, (compared, refused)
    assert moved > compared // 10, (moved, compared)          # the corpus does exercise the exchanges


if __name__ == "__main__":
    test_the_shapes_measured_by_hand()
    test_generated_patterns_store_in_cpythons_order()
    print("ok")
