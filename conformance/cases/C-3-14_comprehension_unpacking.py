# clause: C-3-14
# spec: section 3
# status: P2+
# source: dialect specification v0.4 section 3 (PEP 798, new in 3.15, is [P2+])
"""Unpacking in comprehensions (PEP 798). Phase 1 refuses it with the milestone-naming error;
CPython's trace is recorded for the milestone."""
rows = [[1, 2], [3]]
print([*r for r in rows], sorted({*r for r in rows}), {**d for d in [{"a": 1}, {"b": 2}]}, list(*r for r in rows))
