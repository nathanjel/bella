"""Simulates a registered deviation on the reference CPython (conformance/harness.py).

The harness puts this directory on PYTHONPATH and lists, in BELLA_SIMULATE_BLOCK, the modules
phase 1 does not have (deviation D-20: the manifest's omissions and the codecs outside the
phase-1 set). Blocking them here, before the case runs, makes CPython behave as the compiled
program must: each import of one raises ImportError, as if the module were not installed.
Nothing else is imported, so a case's own observations of sys.modules are not disturbed."""
import os
import sys

for _name in filter(None, os.environ.get("BELLA_SIMULATE_BLOCK", "").split(",")):
    sys.modules[_name] = None  # type: ignore[assignment]
