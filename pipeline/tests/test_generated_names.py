"""A unit's generated names are its own.

The frontend numbers the names it makes (`_tmp`: a comprehension's helper, a comparison's temporary, an annotate function's
argument) from a counter. The counter was never reset, so a unit's text depended on what the process had lowered before
it: `make slice` on a cold cache, which lowers the standard library's units in the same process first, rewrote the
committed `pipeline/examples/out/fact_big.cpp` with `_format8601` where a warm cache gives `_format3` (2026-11-22). The
counter starts again for each unit, where the frontend's other per-unit state is cleared.

Run under pytest or directly: python3 -m pipeline.tests.test_generated_names
"""
from __future__ import annotations

from pipeline.l1.frontend import lower
from pipeline.l1.pretty import render

UNIT = '''
def squares(xs: list[int]) -> list[int]:
    return [x * x for x in xs if 0 < x < 10]


def annotated(a: int, b: "str") -> None:
    total = sum(v for v in (a, 1))
    first, second = total, b
    print(first, second)


for i, j in [(1, 2)]:
    print(squares([i, j]))
'''

OTHER = '''
class C:
    values = [n for n in range(3)]

    def method(self, x: float = 1.5) -> dict[str, float]:
        return {str(k): x for k in self.values if 0 <= k < 2}


print({c for c in "abc"}, C().method())
'''


def test_a_units_names_do_not_depend_on_what_was_lowered_before() -> None:
    alone = lower(UNIT, "unit.py")
    lower(OTHER, "other.py")
    lower(OTHER + UNIT, "both.py")
    again = lower(UNIT, "unit.py")
    assert render(alone) == render(again)
    assert alone.synthetic == again.synthetic
    assert alone.synthetic, "the unit has generated names: the test would prove nothing without"


if __name__ == "__main__":
    test_a_units_names_do_not_depend_on_what_was_lowered_before()
    print("ok")
