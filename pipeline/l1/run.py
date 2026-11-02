"""Run a program through the frontend, wf1 and eval1, as `python program.py args` would.

    python pipeline/l1/run.py [--modules program|closure] [--lock LOCK] program.py [args...]

The conformance harness uses it as a runner (``harness.py check --runner "... run.py {case}"``).
The program runs as `__main__` in a module of its own, with sys.argv and sys.path[0] as CPython
sets them (no script directory under -P). Imported modules come from pipeline/l1/modules.py:
with `--modules program` (the default) eval1 runs the program's own modules and the standard
library is the host's; with `--modules closure` eval1 also runs every compiled standard-library
module of the lock and the Python shims, all lowered before the program starts (decision P-1).

A construct the frontend does not lower stops the run: stderr ``bella-eval1: unsupported: ...``
and exit 70, the staging refusal's status. An exception the program does not catch ends it as
CPython ends it, with exit 1 and the exception's last line on stderr; the frames above it are
eval1's own, so only the D-06-masked shape is comparable.
"""
from __future__ import annotations

import os
import sys
import traceback
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REFUSED = 70


def _refuse(message: str) -> int:
    sys.stdout.flush()
    print(f"bella-eval1: unsupported: {message}", file=sys.stderr)
    return REFUSED


def main(argv: list[str]) -> int:
    sys.path.insert(0, str(ROOT))
    import importlib.machinery

    from pipeline.l1.eval1 import Interpreter
    from pipeline.l1.frontend import lower
    from pipeline.l1.grammar import DialectError, Unsupported
    from pipeline.l1.modules import ModuleSystem, Refused
    from pipeline.l1.wf import check
    sys.path.remove(str(ROOT))

    modules, lock = "program", None
    while argv and argv[0].startswith("--"):
        flag, argv = argv[0], argv[1:]
        if flag == "--modules" and argv:
            modules, argv = argv[0], argv[1:]
        elif flag == "--lock" and argv:
            lock, argv = Path(argv[0]), argv[1:]
        else:
            print(f"run.py: unknown option {flag}", file=sys.stderr)
            return 2
    if not argv:
        print("usage: run.py [--modules program|closure] [--lock LOCK] program.py [args...]", file=sys.stderr)
        return 2
    path = Path(argv[0])
    try:
        program = lower(path.read_text(encoding="utf-8"), str(path.resolve()))
        check(program)
    except (Unsupported, DialectError) as exc:
        return _refuse(str(exc))
    interp = Interpreter()
    system = ModuleSystem(interp, modules, lock)
    if modules == "closure":
        failed = system.prelower()
        if failed:
            # decision P-1 compiles these to statement refusals; until step B the module refuses
            print(f"bella-eval1: {len(failed)} closure modules do not lower yet: "
                  f"{', '.join(sorted(failed))}", file=sys.stderr)

    # the process looks as `python program.py` leaves it: argv, sys.path[0], a fresh __main__
    sys.argv = list(argv)
    if sys.path and not sys.flags.safe_path:
        sys.path[0] = str(path.resolve().parent)       # run.py's directory was there
    main_module = types.ModuleType("__main__")
    main_module.__dict__["__builtins__"] = __import__("builtins")
    main_module.__file__ = str(path.resolve())
    main_module.__loader__ = importlib.machinery.SourceFileLoader("__main__", str(path.resolve()))  # type: ignore[assignment]
    sys.modules["__main__"] = main_module
    system.activate()
    sys.setrecursionlimit(max(sys.getrecursionlimit(), 20000))
    try:
        interp.run_in(program, main_module.__dict__)
    except SystemExit as exc:
        code = exc.code
        if code is None or isinstance(code, int):
            return code or 0
        print(code, file=sys.stderr)
        return 1
    except (Unsupported, Refused) as exc:
        return _refuse(str(exc))
    except BaseException as exc:  # noqa: BLE001  # the program's uncaught exception ends it, as in CPython
        sys.stdout.flush()
        print("Traceback (most recent call last):", file=sys.stderr)
        print("".join(traceback.format_exception_only(exc)), end="", file=sys.stderr)
        return 1
    finally:
        sys.stdout.flush()
    return 0


if __name__ == "__main__":
    os.environ.setdefault("PYTHONHASHSEED", "0")
    raise SystemExit(main(sys.argv[1:]))
