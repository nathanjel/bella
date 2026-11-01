"""The staging dry run (spec section 8; prototype, docs/staging.md).

    python -P pipeline/staging/dryrun.py --out A.json --binary A.bin
           [--modules-from LOCK] [--entry SCRIPT] [--program-module NAME ...]
           [--tables all|program]

Run by pipeline/staging/run.py in the phase-1 configuration (the D-20 omissions blocked). It
imports the modules it is given, so their definition-time code runs: every module of a closure
lock, the program's own modules, and the entry script under its own module name, so that its
`if __name__ == "__main__":` block stays false and the program itself does not run. What these
module bodies print is discarded. Meanwhile it records:

* every `exec`/`eval` of a text, by call site (`module:qualname:line`) and text, with the module
  whose body was running: the code the compiler must compile, keyed as the runtime looks it up;
* probes: each `namedtuple` call with literal fields anywhere in the program's source (inside a
  function too), made once here, which stages its text whether or not a module body reaches it;
* the inputs module bodies read (files outside the import system, environment variables,
  standard input), for the ledger;
* for each module source, the build-time answers to annotationlib's fallbacks (annotations.py);
* the static exec sites of every module source, with the number of texts staged at each.

`--out` is the reviewable artefact (JSON); `--binary` holds the same texts compiled, the stand-in
for the C++ the compiler would emit, which the replay loads (marshal, as a .pyc holds code).
"""
from __future__ import annotations

import builtins
import os
import sys

TYPE_CHECKING = False
if TYPE_CHECKING:                  # nothing is imported at runtime before recording starts
    from types import FrameType
    from typing import Any

# Recording starts before anything beyond the interpreter's start-up modules is imported, so the
# texts that this script's own imports generate are recorded too.
_REAL_EXEC = builtins.exec
_REAL_EVAL = builtins.eval
_REAL_COMPILE = builtins.compile
_FUTURE_MASK = 0x3FE0000          # every CO_FUTURE_* flag (Include/cpython/code.h)
PRELOADED = sorted(n for n, m in sys.modules.items() if m is not None)   # None: a D-20 block
sys.dont_write_bytecode = True
_bodies: list[str] = []            # the module bodies running, innermost last
_texts: dict[tuple[str, str, str], tuple[set[str], int]] = {}     # (site, kind, text) -> (by, flags)
_inputs: dict[str, set[str]] = {}
_compiles: dict[str, set[str]] = {}


def _site(frame: FrameType) -> str:
    return f"{frame.f_globals.get('__name__')}:{frame.f_code.co_qualname}:{frame.f_lineno}"


def _body() -> str:
    return _bodies[-1] if _bodies else "<start-up>"


def _record(kind: str, source: Any, frame: FrameType) -> None:
    text = source.decode("utf-8") if isinstance(source, bytes) else source
    if isinstance(text, str):
        by, _ = _texts.setdefault((_site(frame), kind, text), (set(), frame.f_code.co_flags & _FUTURE_MASK))
        by.add(_body())


def _namespaces(frame: FrameType, g: Any, loc: Any) -> tuple[Any, Any]:
    if g is None:
        g = frame.f_globals
        if loc is None:      # PEP 667: a function's locals() is a snapshot
            loc = dict(frame.f_locals) if frame.f_code.co_flags & 0x1 else frame.f_locals
    return g, loc


def _exec(source: Any, globals: Any = None, locals: Any = None, /, *, closure: Any = None) -> None:
    frame = sys._getframe(1)
    _record("exec", source, frame)
    g, loc = _namespaces(frame, globals, locals)
    if closure is None:
        return _REAL_EXEC(source, g, loc)  # noqa: S102  # recorded, then run as CPython runs it
    return _REAL_EXEC(source, g, loc, closure=closure)  # noqa: S102


def _eval(source: Any, globals: Any = None, locals: Any = None, /) -> Any:
    frame = sys._getframe(1)
    _record("eval", source, frame)
    g, loc = _namespaces(frame, globals, locals)
    return _REAL_EVAL(source, g, loc)  # noqa: S307


def _ours(frame: FrameType | None) -> bool:
    """Called from this tool (its main script or its package), not from the program."""
    while frame is not None:
        if str(frame.f_globals.get("__name__")).startswith(("pipeline.", "__main__")):
            return True
        frame = frame.f_back
    return False


def _compile(source: Any, filename: Any, mode: str, *args: Any, **kwargs: Any) -> Any:
    frame = sys._getframe(1)
    if not _ours(frame):
        _compiles.setdefault(_site(frame), set()).add(_body())
    return _REAL_COMPILE(source, filename, mode, *args, **kwargs)


def _loader_exec(code: Any, globals: dict[str, Any], /) -> None:
    """The import system's exec of a module body: real, and bracketed so that what the body
    does is attributed to it."""
    _bodies.append(str(globals.get("__name__")))
    try:
        _REAL_EXEC(code, globals)  # noqa: S102
    finally:
        _bodies.pop()


builtins.exec = _exec          # type: ignore[assignment]
builtins.eval = _eval          # type: ignore[assignment]
builtins.compile = _compile
for _loader in ("_frozen_importlib", "_frozen_importlib_external"):
    vars(sys.modules[_loader]).update(exec=_loader_exec, compile=_REAL_COMPILE)


def _by_import_system(frame: FrameType | None) -> bool:
    while frame is not None:
        if str(frame.f_globals.get("__name__")).startswith(("_frozen_importlib", "importlib._bootstrap")):
            return True
        frame = frame.f_back
    return False


def _audit(event: str, args: tuple[Any, ...]) -> None:
    if not _bodies or event not in ("open", "os.listdir", "os.scandir", "subprocess.Popen", "os.system", "socket.connect"):
        return
    if _by_import_system(sys._getframe(1)):
        return
    _inputs.setdefault(_body(), set()).add(f"open {args[0]}" if event == "open" else event)


sys.addaudithook(_audit)
_environ_get = type(os.environ).__getitem__


def _environ_read(self: Any, key: str) -> str:
    if _bodies:
        _inputs.setdefault(_body(), set()).add(f"environ {key}")
    return _environ_get(self, key)


type(os.environ).__getitem__ = _environ_read  # type: ignore[method-assign]

# Only now the helpers: their imports are module bodies like any other, and are recorded.
_REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, _REPO)
import argparse  # noqa: E402
import collections  # noqa: E402
import hashlib  # noqa: E402
import importlib  # noqa: E402
import importlib.util  # noqa: E402
import io  # noqa: E402
import json  # noqa: E402
import marshal  # noqa: E402
from pathlib import Path  # noqa: E402

from pipeline.staging import annotations as annotation_tables  # noqa: E402
from pipeline.staging import intrinsics, scan  # noqa: E402

sys.path.remove(_REPO)


def _import(name: str, failures: dict[str, str]) -> None:
    try:
        importlib.import_module(name)
    except BaseException as exc:  # noqa: BLE001  # a module that fails here fails at runtime too
        failures[name] = type(exc).__name__


def _import_entry(path: str, failures: dict[str, str]) -> str:
    name = os.path.splitext(os.path.basename(path))[0]
    if name in sys.modules:
        name = "__bella_entry__"
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    try:
        spec.loader.exec_module(module)
    except BaseException as exc:  # noqa: BLE001  # SystemExit, or an uncaught error the program also raises
        failures[name] = type(exc).__name__
    return name


def _source_of(name: str) -> str | None:
    module = sys.modules.get(name)
    path = getattr(module, "__file__", None)
    return path if isinstance(path, str) and path.endswith(".py") and os.path.exists(path) else None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--binary", required=True)
    ap.add_argument("--modules-from", help="a closure lock: import every module it lists")
    ap.add_argument("--entry", help="the program's entry script, imported under its own name")
    ap.add_argument("--program-module", action="append", default=[])
    ap.add_argument("--tables", choices=("all", "program"), default="program")
    ap.add_argument("--shims", help="the phase-1 shim sources: their tables and exec sites are covered too")
    args = ap.parse_args()

    failures: dict[str, str] = {}
    lock_modules: list[str] = []
    if args.modules_from:
        with open(args.modules_from, encoding="utf-8") as f:
            lock = json.load(f)
        lock_modules = [n for n, m in lock["modules"].items()
                        if m["status"] in ("compiled", "mapped", "core", "shim") and n != "__main__"]
    program: dict[str, str] = {}          # module name at runtime -> source path
    real_out, real_err, real_in = sys.stdout, sys.stderr, sys.stdin
    sys.stdout = sys.stderr = io.StringIO()      # what module bodies print is discarded
    sys.stdin = io.StringIO()
    try:
        for name in lock_modules:
            _import(name, failures)
        if args.entry:
            sys.path.insert(0, os.path.dirname(os.path.abspath(args.entry)))
        for name in args.program_module:
            _import(name, failures)
            if (path := _source_of(name)) is not None:
                program[name] = path
        if args.entry:
            sys.argv = [args.entry]        # the arguments are the run's input, not the build's
            _import_entry(args.entry, failures)
            program["__main__"] = os.path.abspath(args.entry)

        # the sources this artefact covers: exec sites, literal namedtuples, annotation tables
        covered = {n: p for n in lock_modules if (p := _source_of(n)) is not None} if args.tables == "all" else {}
        if args.shims:       # a shim replaces CPython's module of that name
            covered |= {f.stem: str(f) for f in sorted(Path(args.shims).glob("*.py"))}
        covered |= program
        sites: dict[str, str] = {}
        calls: list[scan.NamedTupleCall] = []
        for name, path in sorted(covered.items()):
            with open(path, encoding="utf-8") as f:
                module_sites, module_calls = scan.scan(f.read(), name, path)
            sites |= dict(module_sites)
            calls += module_calls
        # probes: each literal namedtuple call, made once, stages its text wherever it sits
        for call in calls:
            if intrinsics.namedtuple_fields(call.fields, call.rename) is not None:
                _bodies.append("<probe>")
                try:
                    collections.namedtuple(call.typename, call.fields, rename=call.rename)
                finally:
                    _bodies.pop()
    finally:
        sys.stdout, sys.stderr, sys.stdin = real_out, real_err, real_in

    tables: dict[str, annotation_tables.AnnotateEntry] = {}
    for path in sorted(set(covered.values())):
        tables |= annotation_tables.tables_for_source(path)
    # Only what the closure's modules, the program or a probe generated. Not this tool's own
    # modules, nor modules phase 1 does not have, which CPython's real versions of the shimmed
    # modules (asyncio, socket, ...) import here: ssl, selectors, concurrent.futures.
    wanted = set(lock_modules) | set(program) | {"<probe>"}
    texts = []
    for (site, kind, text), (bodies, flags) in sorted(_texts.items()):
        by = sorted(b for b in bodies if b in wanted or (not lock_modules and not b.startswith("pipeline.")))
        if by:
            texts.append((site, kind, text, by, flags))
    staged_at = collections.Counter(site for site, _, _, _, _ in texts)
    table = intrinsics.intrinsic_table(calls)
    artefact = {
        "format": 1,
        "python": ".".join(map(str, sys.version_info[:3])),
        "preloaded": PRELOADED,
        "texts": [{"site": site, "kind": kind, "sha256": hashlib.sha256(text.encode()).hexdigest(),
                   "by": by, "flags": flags, "text": text} for site, kind, text, by, flags in texts],
        "exec_sites": [{"site": s, "kind": k, "texts": staged_at.get(s, 0)} for s, k in sorted(sites.items())],
        "compile_calls": {site: sorted(b for b in by if not b.startswith("pipeline."))
                          for site, by in sorted(_compiles.items()) if any(not b.startswith("pipeline.") for b in by)},
        "failed_imports": dict(sorted(failures.items())),
        "inputs": {m: sorted(v) for m, v in sorted(_inputs.items())},
        "namedtuple_calls": len(calls),
        "intrinsics": {" ".join(k): v for k, v in sorted(table.items())},
        "annotations": dict(sorted(tables.items())),
    }
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(artefact, f, indent=1)
        f.write("\n")
    compiled = {(site, text): _REAL_COMPILE(text, "<string>", kind, flags=flags, dont_inherit=True)
                for site, kind, text, _, flags in texts}
    intrinsic_code = {fields: _REAL_COMPILE(text, "<string>", "eval", dont_inherit=True) for fields, text in table.items()}
    with open(args.binary, "wb") as binary:
        marshal.dump({"texts": compiled, "annotations": tables, "intrinsics": intrinsic_code}, binary)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
