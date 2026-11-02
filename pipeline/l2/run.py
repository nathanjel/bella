"""Run a program through the frontend, wf1, to-anf, wf2 and eval2, as `python program.py` would.

    python pipeline/l2/run.py [--modules program|closure] [--lock LOCK] program.py [args...]

The same runner as pipeline/l1/run.py (its docstring has the conventions: refusals exit 70, an
uncaught exception exits 1 with its last line), with the program and the modules the module
system runs lowered on to L2 and run by eval2.
"""
from __future__ import annotations

import sys

STARTUP = list(sys.modules)     # what CPython imported before this script's first line

import os  # noqa: E402
from pathlib import Path  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]

if __name__ == "__main__":
    os.environ.setdefault("PYTHONHASHSEED", "0")
    sys.path.insert(0, str(ROOT))
    import pipeline.l1.run as run1
    sys.path.remove(str(ROOT))
    raise SystemExit(run1.main(sys.argv[1:], level=2, startup=STARTUP))
