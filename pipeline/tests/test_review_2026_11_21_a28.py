"""Review A28 of 2026-11-21 (range ebf460e..2977264), compiled against CPython: a program for each finding fixed.

Codex's Astra at low effort read the step that makes a tuple keep its hash (RL-574, C-6-24) and the fixes of review
A27; the review log has its six findings as RL-622 to RL-627. Held here: an unclosed file's ResourceWarning at the
program's end against a program that replaced `_warnings.warn` (RL-625; with a filter that ignores it, since a function
of the program's kept in `_warnings` also moves the file's end to CPython's last collection, which is RL-514's), and the
program that tells a first store that fails from the look before it, which RL-614's row did not (RL-627). RL-622 is the
harness's own
(conformance/tests/test_harness.py). RL-624 (the native stack) and RL-626 (a starred tuple's identity) are open, each
a step of its own; RL-623 is a wording for the author.

Run under pytest or directly: python3 -m pipeline.tests.test_review_2026_11_21_a28
"""
from __future__ import annotations

from typing import Any

from pipeline.tests.test_review_2026_11_19 import same

FINDINGS: list[tuple[str, str, str]] = [
    ('RL-625', 'at the end of the program too, the warning of a file left open is not what the program put under _warnings.warn', r'''
import _warnings, warnings
warnings.simplefilter('ignore', ResourceWarning)
def replacement(*a): print('replacement', flush=True)
_warnings.warn = replacement
f = open(__file__)
print('the end of the text')                   # reaches: the end of the text
'''),
    ('RL-627', 'a new link whose store fails: the comparison that raises is the look after the call, the store, or none', r'''
from functools import lru_cache
class K:
    def __init__(self,n):self.n=n
    def __hash__(self):return 0
    def __eq__(self,o):
        events.append('eq')
        if events.count('eq')==target:raise ValueError
        return self.n==o.n
class R:
    def __del__(self):events.append('del')
@lru_cache(3)
def h(k):
    events.append('call')
    return R()
for target in (2,3,4):
    events=[]
    h(K(1))
    events.clear()
    try:h(K(2))
    except ValueError:pass
    print(target,events,tuple(h.cache_info()))
    h.cache_clear()
# reaches: 3 ['eq', 'call', 'eq', 'eq', 'del'] (0, 2, 3, 1)
# reaches: 4 ['eq', 'call', 'eq', 'eq'] (0, 2, 3, 2)
'''),
]


def pytest_generate_tests(metafunc: Any) -> None:
    if "finding" in metafunc.fixturenames:
        metafunc.parametrize("finding", FINDINGS, ids=[f"{rl}-{name}" for rl, name, _ in FINDINGS])


def test_finding(finding: tuple[str, str, str]) -> None:
    same(finding[2])


if __name__ == "__main__":
    for row in FINDINGS:
        same(row[2])
        print("ok", row[0])
