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
* for each module source, the second entry point of every `__annotate__` CPython generates for it,
  checked against CPython at build time (annotations.py; decision S-1);
* the static exec sites of every module source, with the number of texts staged at each.

`--out` is the reviewable artefact (JSON); `--binary` holds the same texts compiled, the stand-in
for the C++ the compiler would emit, which the replay loads (marshal, as a .pyc holds code).
"""
from __future__ import annotations

import _thread                     # a built-in the interpreter has loaded already: the list of what was preloaded is unchanged
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
_texts: dict[tuple[str, str, str | bytes], tuple[set[str], int, Any]] = {}   # (site, kind, source) -> (by, flags, code)
_compiled: dict[tuple[Any, ...], tuple[set[str], tuple[Any, ...]]] = {}   # compile(): key -> (by, outcome)
_inputs: dict[str, set[str]] = {}
_compiles: dict[str, set[str]] = {}            # compile() calls not staged, by site with line
ENTRY = "__bella_entry__"          # the entry script's module name here; __main__ when it runs
_AST_RESULT = 0x400 | 0x8000       # PyCF_ONLY_AST, PyCF_OPTIMIZED_AST: compile() returns a tree


def _module_of(frame: FrameType) -> str:
    name = str(frame.f_globals.get("__name__"))
    return "__main__" if name == ENTRY else name


def _site(frame: FrameType) -> str:
    """The function a call is made from, `module:qualname`, as the runtime names it. The line is
    not part of it: the text, the operation and the compilation parameters identify the code,
    and a shim's lines differ from CPython's module's (review 2026-11-01 gemini-4-argon-high-04)."""
    return f"{_module_of(frame)}:{frame.f_code.co_qualname}"


def _where(frame: FrameType) -> str:
    return f"{_site(frame)}:{frame.f_lineno}"


def _body() -> str:
    return _bodies[-1] if _bodies else "<start-up>"


def _compile_as_builtin(kind: str, source: str | bytes, flags: int) -> Any:
    """What exec or eval compiles a string or bytes source to, in the caller's context: its
    __future__ flags, not this file's (review 2026-11-02 astra-low-06, A6-2), and the builtin's
    preprocessing: eval strips leading spaces and tabs, and bytes are decoded by their PEP 263
    declaration, as compile() decodes them (A6-3)."""
    if kind == "eval":
        source = source.lstrip(b" \t") if isinstance(source, bytes) else source.lstrip(" \t")
    return _REAL_COMPILE(source, "<string>", kind, flags, True)


def _staged_code(kind: str, source: Any, frame: FrameType) -> Any:
    """The code exec or eval runs for `source` here, recorded under the original source (its
    identity: str or bytes, before any preprocessing) when it is a string."""
    if not isinstance(source, (str, bytes)):
        return source
    flags = frame.f_code.co_flags & _FUTURE_MASK
    code = _compile_as_builtin(kind, source, flags)
    by, _, _ = _texts.setdefault((_site(frame), kind, source), (set(), flags, code))
    by.add(_body())
    return code


def _namespaces(frame: FrameType, g: Any, loc: Any) -> tuple[Any, Any]:
    if g is None:
        g = frame.f_globals
        if loc is None:      # PEP 667: a function's locals() is a snapshot
            loc = dict(frame.f_locals) if frame.f_code.co_flags & 0x1 else frame.f_locals
    return g, loc


def _exec(source: Any, globals: Any = None, locals: Any = None, /, *, closure: Any = None) -> None:
    frame = sys._getframe(1)
    if closure is not None and isinstance(source, (str, bytes)):
        raise TypeError("closure can only be used when source is a code object")
    code = _staged_code("exec", source, frame)
    g, loc = _namespaces(frame, globals, locals)
    if closure is None:
        return _REAL_EXEC(code, g, loc)  # noqa: S102  # recorded, then run as CPython runs it
    return _REAL_EXEC(code, g, loc, closure=closure)  # noqa: S102


def _eval(source: Any, globals: Any = None, locals: Any = None, /) -> Any:
    frame = sys._getframe(1)
    code = _staged_code("eval", source, frame)
    g, loc = _namespaces(frame, globals, locals)
    return _REAL_EVAL(code, g, loc)  # noqa: S307


def _ours() -> bool:
    """A call this tool makes (its scanners parse sources after the imports), not the program's:
    the program's definition-time code runs inside a module body, or a probe."""
    return not _bodies or _bodies[-1].startswith("pipeline.")


def compile_key(site: str, source: Any, filename: Any, mode: Any, flags: int, dont_inherit: bool, optimize: int,
                module: Any, feature_version: int, caller_flags: int) -> tuple[Any, ...] | None:
    """What a compile() call's result depends on, the source as given (str or bytes); None if it
    is not stageable (a tree, not code)."""
    if not isinstance(source, (str, bytes)) or flags & _AST_RESULT:
        return None
    inherited = 0 if dont_inherit else caller_flags
    return (site, "compile", source, str(filename), str(mode), flags | inherited, optimize, module, feature_version)


def _compile(source: Any, filename: Any, mode: str, flags: int = 0, dont_inherit: bool = False, optimize: int = -1,
             *, module: Any = None, _feature_version: int = -1) -> Any:
    """compile() is staged like exec and eval: CPython's own code calls it while modules are
    defined (typing._make_forward_ref compiles each string forward reference). The outcome, code
    or the exception and its arguments, is recorded under what it depends on."""
    frame = sys._getframe(1)
    args = (source, filename, mode, flags, dont_inherit, optimize)
    if _ours():
        return _REAL_COMPILE(*args, module=module, _feature_version=_feature_version)
    key = compile_key(_site(frame), source, filename, mode, flags, dont_inherit, optimize, module, _feature_version,
                      frame.f_code.co_flags & _FUTURE_MASK)
    try:
        result = _REAL_COMPILE(source, filename, mode, flags | (0 if dont_inherit else frame.f_code.co_flags & _FUTURE_MASK),
                               True, optimize, module=module, _feature_version=_feature_version)
    except Exception as exc:
        if key is not None:
            _compiled.setdefault(key, (set(), ("raises", type(exc).__name__, exc.args)))[0].add(_body())
        else:
            _compiles.setdefault(_where(frame), set()).add(_body())
        raise
    if key is None:
        _compiles.setdefault(_where(frame), set()).add(_body())
    else:
        _compiled.setdefault(key, (set(), ("code", result)))[0].add(_body())
    return result


def _loader_exec(code: Any, globals: dict[str, Any], /) -> None:
    """The import system's exec of a module body: real, and bracketed so that what the body
    does is attributed to it."""
    name = str(globals.get("__name__"))
    _bodies.append("__main__" if name == ENTRY else name)
    try:
        _REAL_EXEC(code, globals)  # noqa: S102
    finally:
        _bodies.pop()


builtins.exec = _exec          # type: ignore[assignment]
builtins.eval = _eval          # type: ignore[assignment]
builtins.compile = _compile
for _loader in ("_frozen_importlib", "_frozen_importlib_external"):
    vars(sys.modules[_loader]).update(exec=_loader_exec, compile=_REAL_COMPILE)


_LOADER = ("_frozen_importlib", "importlib._bootstrap", "zipimport")
_STDLIB = os.path.realpath(os.path.dirname(os.__file__))
_TOOL = os.path.realpath(os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "pipeline"))


class Confined(BaseException):
    """A program's module body asked for an effect on the world outside the build; the dry run of that body ends here. Not an
    Exception: the body's own `except Exception` is not meant to take it for a failure of the operation."""


# The audit events that change the world: files and directories, processes, and what is sent over a socket. Reading it (open
# for reading, listing, stat, a name looked up) and changing the process itself (the environment, the working directory) are
# a module body's own business. "open" is one of them when its flags can write.
_EFFECTS = frozenset({
    "os.remove", "os.rename", "os.rmdir", "os.mkdir", "os.chmod", "os.chown", "os.chflags", "os.truncate", "os.symlink", "os.link",
    "os.utime", "os.setxattr", "os.removexattr", "os.lockf",
    "shutil.copyfile", "shutil.copymode", "shutil.copystat", "shutil.copytree", "shutil.rmtree", "shutil.move", "shutil.make_archive",
    "shutil.unpack_archive", "tempfile.mkstemp", "tempfile.mkdtemp",
    "subprocess.Popen", "os.system", "os.exec", "os.fork", "os.forkpty", "os.posix_spawn", "os.spawn", "os.startfile", "os.kill",
    "os.killpg", "pty.spawn",
    "socket.connect", "socket.bind", "socket.sendto", "socket.sendmsg", "socket.sethostname",
    "fcntl.flock", "fcntl.lockf", "syslog.syslog",
    "shutil.chown", "webbrowser.open",           # they announce what the calls beneath them would be refused for (review R20 #4)
})
_WRITES = os.O_WRONLY | os.O_RDWR | os.O_APPEND | os.O_CREAT | os.O_TRUNC
_LOCK_UN = 8                                    # fcntl.LOCK_UN, without importing fcntl before the program does
# What changes something outside this process and raises no audit event at all, so that no hook sees it (review R20 #2).
# Found by reading every function of Modules/posixmodule.c for PySys_Audit: 148 of this platform's raise none, and these are
# the ones among them that need no descriptor opened for writing first (which is refused) and reach beyond the process:
# nodes in the file system, other processes' scheduling, the terminal's foreground group; and signal's pidfd_send_signal.
# They are replaced by a refusal in posix, os and _signal when the program's code starts.
_UNAUDITED = ("mkfifo", "mknod", "setpriority", "sched_setaffinity", "sched_setparam", "sched_setscheduler", "tcsetpgrp")
_artefact: frozenset[str] = frozenset()         # the tool's own files, while main() writes them
_confined: list[tuple[str, int, str]] = []      # (file, line, what): where a body was stopped, in order
_own: dict[str, bool] = {}


def _of_the_program(path: object) -> bool:
    """A source file of the program's: a file that is neither the standard library's nor this tool's."""
    if not isinstance(path, str):
        return False
    known = _own.get(path)
    if known is None:
        real = os.path.realpath(path)
        known = _own[path] = os.path.isfile(real) and not real.startswith((_STDLIB + os.sep, _TOOL + os.sep))
    return known


def _shown(value: object) -> str:
    try:
        return repr(value)
    except BaseException:  # noqa: BLE001  # an argument of the program's own: whatever its repr does
        return "<an object whose repr raised>"


def _effect(event: str, args: tuple[Any, ...]) -> str:
    """What an event would do, for the note. An event comes with whatever arguments its caller gave: C's own (a socket and its
    address, a host name alone), or a program's sys.audit of the same name (review R19 #2)."""
    if event == "open":
        return f"open({_shown(args[0])}) for writing"
    if not args:
        return f"{event}()"
    addressed = event in ("socket.connect", "socket.bind", "socket.sendto", "socket.sendmsg") and len(args) > 1
    return f"{event}({_shown(args[1] if addressed else args[0])})"


_started = False                                # a module of the program's has begun to run
_MAIN_THREAD = _thread.get_ident()


def _is_effect(event: str, args: tuple[Any, ...]) -> bool:
    if event == "open":                          # by its flags, when it has them
        return len(args) > 2 and isinstance(args[2], int) and bool(args[2] & _WRITES)
    if event == "os.lockf":                      # F_TEST asks whether a lock is held and changes nothing (review R20 #3)
        return not (len(args) > 1 and args[1] == os.F_TEST)
    if event in ("fcntl.flock", "fcntl.lockf"):  # giving a lock up is no effect; none can be held here
        return not (len(args) > 1 and isinstance(args[1], int) and args[1] & _LOCK_UN)
    return event in _EFFECTS


def _own_write(event: str, args: tuple[Any, ...], doer: FrameType) -> bool:
    """The tool writing its artefact: main() itself, on the main thread, opening or moving one of its own two files. Not
    "while the tool writes": a thread the program started would get its own write through that window (review R20 #1)."""
    if not _artefact or doer.f_code is not main.__code__ or _thread.get_ident() != _MAIN_THREAD:
        return False
    if event == "open":
        return isinstance(args[0], str) and args[0] in _artefact
    return event == "os.rename" and len(args) > 1 and all(isinstance(a, str) and a in _artefact for a in args[:2])


def _refusing(event: str) -> Any:
    def refused(*args: Any, **kwargs: Any) -> None:
        _confine(event, args, sys._getframe(1))
    refused.__name__ = refused.__qualname__ = event.rpartition(".")[2]
    return refused


def _refuse_the_unaudited() -> None:
    """In place of what no audit event announces (_UNAUDITED): in posix and os, which hold the same functions under two
    names, and in _signal, from which signal takes its own when the program imports it."""
    import posix  # noqa: PLC0415  # built in, and loaded by the interpreter already
    for module in (posix, os):
        for name in _UNAUDITED:
            if hasattr(module, name):
                setattr(module, name, _refusing("os." + name))
    for holder in (__import__("_signal"), sys.modules.get("signal")):   # _signal is built in too; signal.py copies its names
        if holder is not None and hasattr(holder, "pidfd_send_signal"):
            setattr(holder, "pidfd_send_signal", _refusing("signal.pidfd_send_signal"))  # noqa: B010


def _confine(event: str, args: tuple[Any, ...], doer: FrameType) -> None:
    """Review F17 #7 and the author's decision of 2026-11-10: a program's module bodies run here, at build time, for the
    definition-time code they generate, and what the program would do to the world besides is refused. From the moment one of
    its modules begins to run, every such event in this process is refused, whoever performs it and whenever: in the body, in
    a thread it started, in a finaliser, in anything it left for later (review R19 #1). Only the tool's own writing of its
    artefact is let through (_own_write), and what raises no event of its own is replaced by a refusal beforehand
    (_refuse_the_unaudited, review R20 #2). When the refusal ends a module body (the main thread, a body running), the place is recorded:
    what the body staged before stays, the build goes on with a note, and a text the body would have reached later stops by
    name at run time, saying where the dry run ended. An audit hook is no sandbox: it stops what a program does in the open,
    not what it does through an extension module, ctypes or a descriptor it already holds."""
    if _own_write(event, args, doer):
        return
    if doer.f_code.co_name == "_get_default_tempdir" and doer.f_globals.get("__name__") == "tempfile":
        return                                   # tempfile.gettempdir() tries each candidate with a file it removes: a question, not an effect
    what = _effect(event, args)
    frame: FrameType | None = doer
    while frame is not None and not _of_the_program(frame.f_code.co_filename):
        frame = frame.f_back                     # the statement is the program's: the call into the standard library that does it
    if _bodies and _thread.get_ident() == _MAIN_THREAD:
        name = _bodies[-1]
        module = sys.modules.get(ENTRY if name == "__main__" else name)
        where = (frame.f_code.co_filename, frame.f_lineno) if frame is not None else (str(getattr(module, "__file__", name)), 0)
        if (*where, what) not in _confined:
            _confined.append((*where, what))
    raise Confined(what if frame is None else f"{frame.f_code.co_filename}:{frame.f_lineno}: {what}")


def _audit(event: str, args: tuple[Any, ...]) -> None:
    """An input is whatever a module body, or anything it calls, reads while it runs. Only the
    frame that performed the operation decides whether the loader did it (reading a module's
    source, listing a directory for the path cache): an importer further down the stack is
    there for every module body (review 2026-11-01 astra-low-05, A5-3)."""
    if _started and _is_effect(event, args):
        _confine(event, args, sys._getframe(1))
    if not _bodies:
        return
    if event not in ("open", "os.listdir", "os.scandir", "subprocess.Popen", "os.system", "socket.connect"):
        return
    if str(sys._getframe(1).f_globals.get("__name__")).startswith(_LOADER):
        return
    try:
        subject = str(args[0]) if args else ""  # as the inventory has always shown it; an argument of the program's own may refuse
    except BaseException:  # noqa: BLE001
        subject = "<an object whose str raised>"
    _inputs.setdefault(_body(), set()).add(f"{event} {subject}" if args else event)


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
import tomllib  # noqa: E402
from pathlib import Path  # noqa: E402

from pipeline.staging import annotations as annotation_entries  # noqa: E402
from pipeline.staging import TOOL_FAILED, intrinsics, scan  # noqa: E402

sys.path.remove(_REPO)


def _import(name: str, failures: dict[str, str]) -> None:
    try:
        importlib.import_module(name)
    except BaseException as exc:  # noqa: BLE001  # a module that fails here fails at runtime too
        failures[name] = type(exc).__name__


def _import_entry(path: str, failures: dict[str, str]) -> str:
    """The entry script, under a name no other module has, so that its main guard stays false and
    it cannot shadow a module it imports; its sites and texts are reported under __main__."""
    name = ENTRY
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    try:
        spec.loader.exec_module(module)
    except BaseException as exc:  # noqa: BLE001  # SystemExit, or an uncaught error the program also raises
        failures[name] = type(exc).__name__
    return name


def _program_modules(program: dict[str, str], failures: dict[str, str]) -> None:
    """Every module the entry brought in from outside the standard library is the program's
    (review 2026-11-01 gemini-4-argon-high-04, 3.4): its entry points and probes are built too.
    A PEP 810 lazy import in a program module is resolved here, so that the module it names is
    defined at build time as it will be at its first use. Reading a name as an attribute of the
    module resolves a lazy import (reading the namespace dict does not); for a name that exists
    that is a plain lookup. Repeated until no new module appears."""
    while True:
        loaded = len(sys.modules)
        program |= {name: path for name, m in list(sys.modules.items())
                    if m is not None and name not in program and name != ENTRY and (path := _source_of(name)) is not None
                    and not os.path.realpath(path).startswith((_STDLIB + os.sep, _TOOL + os.sep))}
        for name in list(program):
            module = sys.modules.get(ENTRY if name == "__main__" else name)
            if module is None:
                continue
            for attr in list(vars(module)):
                try:
                    getattr(module, attr)
                except BaseException as exc:  # noqa: BLE001  # the program meets the same error at first use
                    failures[f"{name}: lazy import {attr}"] = type(exc).__name__
        if len(sys.modules) == loaded:
            return


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
    ap.add_argument("--shims", help="the phase-1 shim sources: their entry points and exec sites are covered too")
    ap.add_argument("--safe-path", action="store_true", help="the program runs with -P: its directory is not on sys.path")
    ap.add_argument("--unsupported-from", action="append", default=[],
                    help="a closure lock whose unsupported functions the runtime refuses")
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
        if args.entry and not args.safe_path:
            sys.path.insert(0, os.path.dirname(os.path.abspath(args.entry)))
        global _started
        _started = bool(args.entry or args.program_module)   # from here on the process changes nothing outside the build
        if _started:
            _refuse_the_unaudited()
        for name in args.program_module:
            _import(name, failures)
            if (path := _source_of(name)) is not None:
                program[name] = path
        if args.entry:
            sys.argv = [args.entry]        # the arguments are the run's input, not the build's
            _import_entry(args.entry, failures)
            program["__main__"] = os.path.abspath(args.entry)
            _program_modules(program, failures)

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

    # From here on only this tool runs, and the codecs phase 1 lacks (D-20) are its own again: ast.unparse escapes an f-string's
    # backslashes through unicode_escape (review F17 #15)
    held: dict[str, object] = dict(sys.modules)      # conformance/simulate's sitecustomize stored None for each
    for blocked in [n for n, m in held.items() if m is None and n.startswith("encodings.")]:
        del sys.modules[blocked]

    evaluators: dict[str, annotation_entries.Evaluator] = {}
    declined: list[str] = []
    for path in sorted(set(covered.values())):
        found, refused = annotation_entries.evaluators_for_source(path)
        evaluators |= found
        declined += refused
    # Only what the closure's modules, the program or a probe generated. Not this tool's own
    # modules, nor modules phase 1 does not have, which CPython's real versions of the shimmed
    # modules (asyncio, socket, ...) import here: ssl, selectors, concurrent.futures.
    wanted = set(lock_modules) | set(program) | {"<probe>"}
    texts = []
    for (site, kind, text), (bodies, flags, code) in sorted(_texts.items(), key=lambda kv: (kv[0][0], kv[0][1], repr(kv[0][2]))):
        by = sorted(b for b in bodies if b in wanted or (not lock_modules and not b.startswith("pipeline.")))
        if by:
            texts.append((site, kind, text, by, flags, code))
    staged_at = collections.Counter(site for site, _, _, _, _, _ in texts)
    staged_at.update(key[0] for key, (bodies, _) in _compiled.items() if any(b in wanted for b in bodies) or not lock_modules)
    table = intrinsics.intrinsic_table(calls)
    compiled_kept = {key: (bodies, outcome) for key, (bodies, outcome) in _compiled.items()
                     if any(b in wanted for b in bodies) or (not lock_modules and any(not b.startswith("pipeline.") for b in bodies))}
    # every source this artefact was made from, by content: a cached artefact is used only while
    # all of them are unchanged (review 2026-11-01 astra-low-05, A5-2)
    loaded = {os.path.realpath(p) for n in list(sys.modules) if (p := _source_of(n)) is not None}
    sources = {path: hashlib.sha256(Path(path).read_bytes()).hexdigest()
               for path in sorted(loaded | {os.path.realpath(p) for p in covered.values()})}
    artefact = {
        "format": 2,
        "sources": sources,
        "python": ".".join(map(str, sys.version_info[:3])),
        "preloaded": PRELOADED,
        "texts": [{"site": site, "kind": kind,
                   "sha256": hashlib.sha256(text if isinstance(text, bytes) else text.encode()).hexdigest(),
                   "by": by, "flags": flags, "text": text if isinstance(text, str) else repr(text)}
                  for site, kind, text, by, flags, _ in texts],
        "exec_sites": [{"site": s, "kind": k, "texts": staged_at.get(s.rsplit(":", 1)[0], 0)} for s, k in sorted(sites.items())],
        "compiles": [{"site": key[0], "text": key[2] if isinstance(key[2], str) else repr(key[2]),
                      "parameters": list(key[3:]), "outcome": outcome[0],
                      "by": sorted(bodies)} for key, (bodies, outcome) in sorted(compiled_kept.items(), key=lambda kv: str(kv[0]))],
        "compile_calls_not_staged": {site: sorted(b for b in by if not b.startswith("pipeline."))
                                     for site, by in sorted(_compiles.items()) if any(not b.startswith("pipeline.") for b in by)},
        "failed_imports": dict(sorted(failures.items())),
        "confined": [{"file": file, "line": line, "what": what} for file, line, what in _confined],
        "inputs": {m: sorted(v) for m, v in sorted(_inputs.items())},
        "namedtuple_calls": len(calls),
        "intrinsics": {" ".join(k): v for k, v in sorted(table.items())},
        "annotate_entry_points": {k: {"freevars": list(e.freevars), "source": e.source} for k, e in sorted(evaluators.items())},
        "annotate_declined": declined,
    }
    # written beside the targets and moved into place, the binary before the JSON that `current`
    # checks: steps running at once (make -j) may make the same artefact, and none may read a
    # half-written one
    json_tmp, binary_tmp = f"{args.out}.{os.getpid()}.tmp", f"{args.binary}.{os.getpid()}.tmp"
    global _artefact
    _artefact = frozenset({json_tmp, binary_tmp, str(args.out), str(args.binary)})   # the one thing this process writes
    with open(json_tmp, "w", encoding="utf-8") as f:
        json.dump(artefact, f, indent=1)
        f.write("\n")
    # (site, operation, text) -> (code, future flags): an eval never runs code staged for an exec
    # (review 2026-11-01 astra-low-05, A5-1), and the caller's flags are checked at runtime
    compiled = {(site, kind, text): (code, flags) for site, kind, text, _, flags, code in texts}   # as the dry run ran it
    intrinsic_code = {fields: _REAL_COMPILE(text, "<string>", "eval", dont_inherit=True) for fields, text in table.items()}
    manifest = tomllib.loads(Path(_REPO, "manifest.toml").read_text(encoding="utf-8"))
    unsupported: dict[str, list[str]] = {}
    for lock_path in args.unsupported_from:
        with open(lock_path, encoding="utf-8") as f:
            for module, functions in json.load(f).get("unsupported_functions", {}).items():
                unsupported.setdefault(module, []).extend(fn for fn in functions if fn not in unsupported.get(module, []))
    unstaged = dict(manifest.get("unstaged", {}))
    if _confined:                                # the reason every miss of this program's carries: "*" is no site
        file, line, what = _confined[0]
        unstaged["*"] = f"the dry run stopped at {os.path.basename(file)}:{line} ({what}), so what the module body does after that line was not staged"
    with open(binary_tmp, "wb") as binary:
        marshal.dump({"optimize": sys.flags.optimize, "texts": compiled, "compiled": {k: o for k, (_, o) in compiled_kept.items()},
                      "confined": list(_confined),
                      "annotations": {k: (e.freevars, e.code) for k, e in evaluators.items()},
                      # compiler-generated functions without an entry point; one that matched no
                      # annotation owner is hand-written, which is not the compiler's to declare
                      "declined": dict(d.split(": ", 1) for d in declined if "matched to 0 annotation owners" not in d),
                      "intrinsics": intrinsic_code, "refused": dict(manifest.get("refused", {})),
                      "unstaged": unstaged, "unsupported": unsupported}, binary)
    os.replace(binary_tmp, args.binary)
    os.replace(json_tmp, args.out)
    _artefact = frozenset()
    return 0


if __name__ == "__main__":
    try:
        status = main()
    except Exception:  # noqa: BLE001  # the tool's own failure; the program's are caught where it runs
        import traceback
        traceback.print_exc()
        status = TOOL_FAILED
    # The process ends here and now. What a module body left for the end of it (atexit's handlers, threading's, finalisers
    # of what is still alive, threads still running) is the program's to run when the program runs, not the build's
    # (review R19 #1); the artefact is written and closed, and the two streams are all that is left to flush.
    for stream in (sys.__stdout__, sys.__stderr__):
        try:
            if stream is not None:
                stream.flush()
        except Exception:  # noqa: BLE001, S110
            pass
    os._exit(status)
