"""Run a program through the frontend, wf1 and eval1, as `python program.py args` would.

    python pipeline/l1/run.py program.py [args...]

The conformance harness uses it as a runner (``harness.py check --runner "... run.py {case}"``).
A construct the frontend does not lower stops the run before it starts: stderr
``bella-eval1: unsupported: ...`` and exit 70, the staging refusal's status. An exception the
program does not catch ends it as CPython ends it, with exit 1 and the exception's last line on
stderr; the frames above it are eval1's own, so only the D-06-masked shape is comparable.
"""
from __future__ import annotations

import sys
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

REFUSED = 70


def main(argv: list[str]) -> int:
    from pipeline.l1.eval1 import Interpreter
    from pipeline.l1.frontend import lower
    from pipeline.l1.grammar import DialectError, Unsupported
    from pipeline.l1.wf import check

    if not argv:
        print("usage: run.py program.py [args...]", file=sys.stderr)
        return 2
    path = Path(argv[0])
    try:
        module = lower(path.read_text(encoding="utf-8"), path.name)
        check(module)
    except (Unsupported, DialectError) as exc:
        print(f"bella-eval1: unsupported: {exc}", file=sys.stderr)
        return REFUSED
    sys.argv = list(argv)
    sys.setrecursionlimit(max(sys.getrecursionlimit(), 20000))
    try:
        Interpreter().run_module(module)
    except SystemExit as exc:
        code = exc.code
        if code is None or isinstance(code, int):
            return code or 0
        print(code, file=sys.stderr)
        return 1
    except Unsupported as exc:
        print(f"bella-eval1: unsupported: {exc}", file=sys.stderr)
        return REFUSED
    except BaseException as exc:  # noqa: BLE001  # the program's uncaught exception ends it, as in CPython
        sys.stdout.flush()
        print("Traceback (most recent call last):", file=sys.stderr)
        print("".join(traceback.format_exception_only(exc)), end="", file=sys.stderr)
        return 1
    finally:
        sys.stdout.flush()
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
