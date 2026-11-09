# clause: C-3-50
# spec: section 3
# status: P1
# source: dialect specification section 3 (exception groups), PEP 654, Lib/traceback.py (TracebackException for groups)
"""traceback's format of an exception group that was never raised (no frames, so nothing machine-dependent): the nested boxes
with their numbers, a nested group, format_exception_only, and the width limit (max_group_width 15: "and 2 more exceptions")."""
# ruff: noqa: E501
import traceback

EG = ExceptionGroup

print("".join(traceback.format_exception(EG("fmt", [ValueError(1), EG("in", [TypeError(2)]), KeyError(3)]))), end="")
print("".join(traceback.format_exception_only(EG("only", [ValueError(1)]))), end="")
many = EG("many", [ValueError(i) for i in range(17)])
print("".join(traceback.format_exception(many, limit=1)).count("ValueError"), "".join(traceback.format_exception(many))[-120:].replace("\n", "|"))
