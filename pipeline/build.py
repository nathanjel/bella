#!/usr/bin/env python3
"""bella build: a program through L2 into C++26, compiled and linked against the runtime.

    python3 pipeline/build.py PROGRAM.py [-o BINARY]           build; print the binary's path
    python3 pipeline/build.py --run PROGRAM.py [ARGS...]        build, then run it as the program
    --fidelity=exact|lean  ahead of PROGRAM.py (anywhere without --run): which build; exact when not given
    --syntax-warnings=on|off  in the same places: whether the program gives the compiler's warnings of its own text at
                              each start, as CPython does; on when not given

The program is lowered (frontend, to-anf, lifetimes, wf2) and emitted by pipeline/backend/cpp.py;
the runtime library is runtime/src/*.cpp and the prelude (runtime/prelude/*.py, compiled the
same way), built once per content hash under build/compiled/ and shared by every program. Each
module of the program's own that an import can reach (pipeline/closed_world.py) is a unit of its
own, compiled once per content hash; the main unit hands the runtime their registry (spec
section 8). A construct the pipeline refuses stops the build with exit 70, as the evaluators
refuse.

A build is exact or lean (its fidelity; docs/DECISIONS.md, 2026-11-11). Exact is the default and is
CPython's behaviour up to the registered deviations (docs/deviations.toml). Lean leaves out the looks
for a signal that the units of the program and of the standard library take at a function's entry
and at a loop's turn: those units are compiled with -DBELLA_LEAN, under which bella/runtime.hpp makes
BELLA_LOOK() nothing; the text, the runtime library and the prelude are the same in both, and one
program built both ways keeps both binaries. A lean program differs in two more things, and neither
waits for a signal from outside: it starts with SIGINT as it found it, default_int_handler not
installed (where that is the default action, Ctrl-C ends the program at once and
`_thread.interrupt_main()` does nothing), and a handler is given None for its frame. The looks the
runtime library takes itself, its prelude's among them, are in both builds. All of this is one
deviation. On the command line --fidelity says which, else the environment's BELLA_FIDELITY (for the
harnesses, whose runner is this command), else exact; build() takes it as an argument and reads no
environment.

CPython compiles a main program at each start, and its compiler warns each time of what it finds doubtful in the text
(`"\\d"`, `x is 1`, an assertion of a tuple): SyntaxWarnings, on standard error, before the first statement. A compiled
program gives the same ones at its start (compiler_warnings; docs/DECISIONS.md, 2026-11-21). --syntax-warnings=off, else the
environment's BELLA_SYNTAX_WARNINGS, builds one that never gives them, which is a registered deviation (D-29); nothing else
of the program changes. The build itself, when it only builds, says them once: the main program's, and those of the
program's other modules, which CPython gives when it first compiles a module and a compiled program never.
"""
from __future__ import annotations

import builtins
import fcntl
import functools
import io
import ast
import hashlib
import json
import marshal
import os
import re
import shutil
import subprocess
import sys
import tokenize
import typing
import warnings
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from functools import cache
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from pipeline.backend.cpp import c_bytes, c_string, emit_module, header_macros  # noqa: E402
from pipeline.closed_world import FROZEN, STDLIB, ProgramModule, find_program_modules, namespace_of, omitted_modules, read_source  # noqa: E402
from pipeline.l1 import grammar as L  # noqa: E402
from pipeline.l1.frontend import lower  # noqa: E402
from pipeline.l1.grammar import Unsupported  # noqa: E402
from pipeline.l1.staged import features, source_text  # noqa: E402
from pipeline.l2 import grammar as G  # noqa: E402
from pipeline.l2 import wf as wf2  # noqa: E402
from pipeline.l2.lifetimes import lifetimes  # noqa: E402
from pipeline.l2.lower import to_l2  # noqa: E402
from pipeline.staging import annotations as annotation_entries  # noqa: E402

REFUSED = 70
BUILD = ROOT / "build" / "compiled"
INCLUDE = ROOT / "runtime" / "include"
SOURCES = sorted((ROOT / "runtime" / "src").glob("*.cpp"))
INCLUDED = sorted((ROOT / "runtime" / "src").glob("*.inc"))       # generated tables the sources include
# vendored C libraries built into the runtime (docs/licences.md): zlib 1.3.2, the pin's, for the zlib module (runtime/src/zlib.cpp)
VENDORED_C = sorted((ROOT / "runtime" / "vendor" / "zlib-1.3.2").glob("*.c"))
VENDORED_H = sorted((ROOT / "runtime" / "vendor" / "zlib-1.3.2").glob("*.h"))
# the prelude's modules, in this order, each run as the module it names (runtime/src/call.cpp, run_main)
PRELUDE = [(ROOT / "runtime" / "prelude" / "build_class.py", "builtins"), (ROOT / "runtime" / "prelude" / "builtins.py", "builtins"),
           (ROOT / "runtime" / "prelude" / "iterating.py", "builtins"), (ROOT / "runtime" / "prelude" / "templatelib.py", "builtins"),
           (ROOT / "runtime" / "prelude" / "bootstrap.py", "_frozen_importlib"),
           (ROOT / "runtime" / "prelude" / "bootstrap_external.py", "_frozen_importlib_external")]
# built-in modules CPython writes in C and this runtime in Python: compiled with the prelude, run at the
# first import (runtime/src/imports.cpp)
NATIVE_IN_PYTHON = [ROOT / "runtime" / "prelude" / "itertools.py", ROOT / "runtime" / "prelude" / "_operator.py",
                    ROOT / "runtime" / "prelude" / "_weakref.py", ROOT / "runtime" / "prelude" / "_thread.py",
                    ROOT / "runtime" / "prelude" / "_collections.py", ROOT / "runtime" / "prelude" / "_string.py",
                    ROOT / "runtime" / "prelude" / "_stat.py", ROOT / "runtime" / "prelude" / "_functools.py", ROOT / "runtime" / "prelude" / "errno.py", ROOT / "runtime" / "prelude" / "posix.py", ROOT / "runtime" / "prelude" / "_sre.py",
                    ROOT / "runtime" / "prelude" / "_codecs.py", ROOT / "runtime" / "prelude" / "_io.py",
                    ROOT / "runtime" / "prelude" / "pwd.py", ROOT / "runtime" / "prelude" / "grp.py", ROOT / "runtime" / "prelude" / "_locale.py",
                    ROOT / "runtime" / "prelude" / "zlib.py", ROOT / "runtime" / "prelude" / "_ast.py", ROOT / "runtime" / "prelude" / "_typing.py",
                    ROOT / "runtime" / "prelude" / "_json.py", ROOT / "runtime" / "prelude" / "binascii.py",
                    ROOT / "runtime" / "prelude" / "_struct.py", ROOT / "runtime" / "prelude" / "time.py",
                    ROOT / "runtime" / "prelude" / "_math_integer.py", ROOT / "runtime" / "prelude" / "math.py", ROOT / "runtime" / "prelude" / "cmath.py", ROOT / "runtime" / "prelude" / "unicodedata.py",
                    ROOT / "runtime" / "prelude" / "_md5.py", ROOT / "runtime" / "prelude" / "_sha1.py", ROOT / "runtime" / "prelude" / "_sha2.py",
                    ROOT / "runtime" / "prelude" / "_sha3.py", ROOT / "runtime" / "prelude" / "_blake2.py", ROOT / "runtime" / "prelude" / "_hmac.py",
                    ROOT / "runtime" / "prelude" / "_csv.py", ROOT / "runtime" / "prelude" / "_contextvars.py",
                    ROOT / "runtime" / "prelude" / "_bisect.py", ROOT / "runtime" / "prelude" / "_random.py",
                    ROOT / "runtime" / "prelude" / "_statistics.py", ROOT / "runtime" / "prelude" / "_heapq.py",
                    ROOT / "runtime" / "prelude" / "_opcode.py", ROOT / "runtime" / "prelude" / "_warnings.py",
                    ROOT / "runtime" / "prelude" / "_tokenize.py", ROOT / "runtime" / "prelude" / "_suggestions.py", ROOT / "runtime" / "prelude" / "_imp.py",
                    ROOT / "runtime" / "prelude" / "atexit.py", ROOT / "runtime" / "prelude" / "_signal.py",
                    ROOT / "runtime" / "prelude" / "gc.py"]
# the runtime's own modules written in Python, compiled with the prelude and in no sys.modules: the loads of the annotate
# functions' second entry points (decision S-1), the replay's file and the compiled program's one (runtime/src/imports.cpp),
# and match's MATCH_* instructions, which eval1 and eval2 run too (runtime/src/call.cpp, load_match)
RUNTIME_PYTHON = [ROOT / "pipeline" / "staging" / "annotate_rt.py", ROOT / "runtime" / "prelude" / "match.py"]
# standard-library modules that stand for a C accelerator CPython has and the closure omits (manifest.toml [adaptations],
# decimal and datetime): CPython's C looks for signals nowhere in them, so their units have no looks (pipeline/backend/cpp.py)
LOOK_FREE = frozenset({"_pydecimal", "_pydatetime"})
CXX = os.environ.get("CXX", "g++")
STD = os.environ.get("CXXSTD", "c++26")
# -ffp-contract=off: a*b + c is two operations with two roundings, as the reference computes it. A compiler that
# may fuse them gives -0.0 + 0.0 another sign and rounds a subnormal differently (the runner's g++ did, in complex
# division; -mfma reproduces it): the program's numbers must not depend on what the compiler's target has.
FP_FLAGS = ["-ffp-contract=off"]
RUNTIME_FLAGS = ["-O2", "-g", "-Wall", "-Wextra", *FP_FLAGS]
VENDORED_FLAGS = ["-O2", "-w", *FP_FLAGS]          # the vendored C, with its own warnings off
# -fno-tree-pta: GCC 16's -O1 is super-linear on a long function full of temporaries with destructors.
# A 3143-line module body took over 25 minutes and 24 MB; without the analysis, 15 seconds and 1.2 MB,
# with no measurable cost at run time (fib and an object, dict and exception workload, within noise).
PROGRAM_FLAGS = ["-O1", "-w", "-fno-tree-pta", *FP_FLAGS]
PRELUDE_FLAGS = ["-O1", "-g", "-fno-tree-pta", *FP_FLAGS]     # the prelude's units are lowered Python, the program's kind of code: -O2 takes GCC 16
#                                                               nine minutes on _io.py's unit alone, -O1 under a minute
LIBRARY_FLAGS = ["-O0", "-w", *FP_FLAGS]      # the standard library's units: a fifth of the compile time; speed is not a goal yet
# A build's fidelity. The whole difference is this define, and only build() gives it: to the units compiled from Python
# sources that are not the prelude's (the program's, the standard library's, the staged texts) and to the main unit, which
# hands the runtime BELLA_IS_LEAN. runtime_library() takes no fidelity: the library and the prelude are one for both, so
# nothing in the headers but the macros BELLA_LOOK and BELLA_IS_LEAN may depend on the define (an inline function that did
# would be two definitions of one name, and the linker keeps either). The emitted text is the same in both, so the lowered
# cache is shared, and the three names are escaped in a program's identifiers (pipeline/backend/cpp.py, _KEYWORDS).
FIDELITIES = ("exact", "lean")
SYNTAX_WARNINGS = ("on", "off")                  # --syntax-warnings: the compiler's warnings of the main program's text at each start, or never
LEAN_DEFINE = "-DBELLA_LEAN"


def _constant_names(tree: ast.Module, expr: ast.expr) -> tuple[str, ...]:
    """A `__slots__` value as the prelude writes one: a literal, a module-level name bound to one, or a sum of those."""
    if isinstance(expr, ast.Name):
        for node in tree.body:
            if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == expr.id for t in node.targets):
                return _constant_names(tree, node.value)
        raise Unsupported(f"the prelude's __slots__: {expr.id} is no constant of its module")
    if isinstance(expr, ast.BinOp) and isinstance(expr.op, ast.Add):
        return _constant_names(tree, expr.left) + _constant_names(tree, expr.right)
    value = ast.literal_eval(expr)
    return (value,) if isinstance(value, str) else tuple(value)


@functools.cache
def prelude_state() -> frozenset[str]:
    """The names the prelude's classes declare as `__slots__`. A built-in type CPython writes in C keeps its state in the
    fields of a struct, which have no names (RL-507; the author's decision of 2026-11-20): in a prelude unit an attribute of
    one of these names is the type's own field where the object's type keeps one, and the emitter says so
    (pipeline/backend/cpp.py, Emitter.state). The runtime library's key holds every file read here."""
    names: set[str] = set()
    for p in [*(p for p, _ in PRELUDE), *NATIVE_IN_PYTHON, *RUNTIME_PYTHON]:
        tree = ast.parse(p.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                for item in node.body:
                    if isinstance(item, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "__slots__" for t in item.targets):
                        names.update(_constant_names(tree, item.value))
    return frozenset(names - {"__dict__", "__weakref__"})


def to_cpp(source: str, filename: str, namespace: str, prelude: bool = False, mode: str = "exec",
           future: frozenset[str] = frozenset(), looks: bool = True, tree: ast.Module | None = None) -> str:
    # the passes walk the tree by recursion, and a chain of operators, calls or elif branches is as deep as it is long: the
    # limit eval1's run has (pipeline/l1/run.py), and past it a refusal by name, not a traceback (review F17 #14)
    limit = sys.getrecursionlimit()
    sys.setrecursionlimit(max(limit, 20000))
    try:
        module: G.Module = lifetimes(to_l2(lower(source, filename, mode=mode, inherit_future=future, tree=tree)))
        wf2.check(module, lifetimes=True)
        return emit_module(module, namespace, filename, prelude, looks, prelude_state() if prelude else frozenset())
    except RecursionError:
        raise Unsupported(f"{filename}: a chain of operators, calls or branches too long for the compiler's passes") from None
    finally:
        sys.setrecursionlimit(limit)


def lowered_unit(source: str, filename: str, namespace: str, mode: str = "exec", future: frozenset[str] = frozenset(),
                 looks: bool = True) -> str:
    """to_cpp, kept under build/compiled/lowered by what decides its text: a closure's modules are
    the same for every program that imports them, and lowering them takes seconds each time. The
    compiler's macros are part of it: they decide which names the emitter escapes."""
    key = _key(source.encode(), filename.encode(), namespace.encode(), mode.encode(), " ".join(sorted(future)).encode(), *_pipeline_bytes(),
               " ".join(sorted(header_macros())).encode(), b"looks" if looks else b"no looks")
    kept = BUILD / "lowered" / f"{namespace.replace('::', '_')}-{key}.cpp"
    if kept.exists():
        return kept.read_text(encoding="utf-8")
    text = to_cpp(source, filename, namespace, mode=mode, future=future, looks=looks)
    kept.parent.mkdir(parents=True, exist_ok=True)
    tmp = kept.with_name(kept.name + f".{os.getpid()}.tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, kept)
    return text


# ---- the second entry points of a module's annotate functions (decision S-1, docs/staging.md section 6) ----
@dataclass(frozen=True)
class EntryRow:
    filename: str
    qualname: str
    first_line: int
    freevars: tuple[str, ...]
    namespace: str | None                  # the unit that defines it; None: the build declined it
    index: int
    why: str


def annotate_entries(source: str, filename: str, namespace: str) -> tuple[list[EntryRow], str | None]:
    """The rows a module's compiler-generated annotate functions get in the main unit's table, and the unit of their entry
    points (none if no function has one). pipeline/staging/annotations.py writes and checks each evaluator from the source,
    against the code CPython compiles from it, as the replay's are; here they are lowered with the positions of the
    annotations they evaluate, so that a traceback through one has CPython's lines and columns. The unit defines each in turn
    and appends it to `_entries`; the runtime gives it `_rt`, annotate_rt.py compiled with the prelude. A compiled function
    finds its entry point by its code's file, qualified name and first line, which CPython's positions disambiguate and this
    key does not: an evaluator whose key another code object of the module has is declined. Kept under build/compiled/entries
    by what decides it, as a lowered unit is."""
    key = _key(source.encode(), filename.encode(), namespace.encode(), *_pipeline_bytes(), " ".join(sorted(header_macros())).encode())
    kept = BUILD / "entries" / f"{namespace.replace('::', '_')}-{key}.json"
    if kept.exists():
        data = json.loads(kept.read_text(encoding="utf-8"))
        return [EntryRow(r[0], r[1], r[2], tuple(r[3]), r[4], r[5], r[6]) for r in data["rows"]], data["cpp"]
    found, declined = annotation_entries.evaluators_for_text(source, filename)
    counts: dict[tuple[str, int], int] = {}
    pending = [compile(source, filename, "exec", dont_inherit=True)]
    while pending:
        code = pending.pop()
        counts[(code.co_qualname, code.co_firstlineno)] = counts.get((code.co_qualname, code.co_firstlineno), 0) + 1
        pending += [c for c in code.co_consts if isinstance(c, type(code))]
    rows: list[EntryRow] = []
    body: list[ast.stmt] = []
    for evaluator in sorted(found.values(), key=lambda e: (e.firstlineno, e.qualname)):
        assert evaluator.tree is not None
        if counts.get((evaluator.qualname, evaluator.firstlineno), 0) != 1:
            rows.append(EntryRow(filename, evaluator.qualname, evaluator.firstlineno, evaluator.freevars, None, -1,
                                 "another function of the module has its qualified name and first line, by which a compiled program finds it"))
            continue
        rows.append(EntryRow(filename, evaluator.qualname, evaluator.firstlineno, evaluator.freevars, namespace, len(body) // 2, ""))
        keep = ast.Expr(ast.Call(ast.Attribute(ast.Name("_entries", ast.Load()), "append", ast.Load()), [ast.Name("__annotate__", ast.Load())], []))
        body += [evaluator.tree, ast.fix_missing_locations(ast.copy_location(keep, evaluator.tree))]
    # a compiler-generated function without one (a function named __annotate__ that matched no owner is the program's own)
    for line in declined:
        where, reason = line.split(": ", 1)
        if "matched to 0 annotation owners" not in reason:
            _, qualname, first, _ = where.rsplit("::", 3)
            rows.append(EntryRow(filename, qualname, int(first), (), None, -1, reason))
    cpp = to_cpp("", filename, namespace, tree=ast.Module(body, [])) if body else None
    kept.parent.mkdir(parents=True, exist_ok=True)
    tmp = kept.with_name(kept.name + f".{os.getpid()}.tmp")
    tmp.write_text(json.dumps({"rows": [[r.filename, r.qualname, r.first_line, list(r.freevars), r.namespace, r.index, r.why] for r in rows],
                               "cpp": cpp}), encoding="utf-8")
    os.replace(tmp, kept)
    return rows, cpp


def _entries_cpp(rows: list[EntryRow]) -> tuple[str, str]:
    """The table of entry points, and the line of main() that registers it."""
    if not rows:
        return "", ""
    decls = sorted({f"namespace {r.namespace} {{ ::bella::Ref module_body(::bella::Module* m); }}" for r in rows if r.namespace})
    items = ",\n".join(f"    {{{c_string(r.filename)}, {c_string(r.qualname)}, {r.first_line}, {{{', '.join(c_string(n) for n in r.freevars)}}}, "
                       f"{'::' + r.namespace + '::module_body' if r.namespace else 'nullptr'}, {r.index}, {c_string(r.why)}}}" for r in rows)
    table = f"static const ::bella::AnnotateEntry ANNOTATE_ENTRIES[] = {{\n{items}\n}};\n"
    return "\n".join(decls) + "\n" + table, f"    ::bella::register_annotate_entries(std::span<const ::bella::AnnotateEntry>(ANNOTATE_ENTRIES, {len(rows)}));\n"


def _key(*parts: bytes) -> str:
    h = hashlib.sha256()
    for p in parts:
        h.update(hashlib.sha256(p).digest())
    return h.hexdigest()[:16]


@cache
def _pipeline_bytes() -> tuple[bytes, ...]:
    """Everything that decides what a program compiles to: the compiler's own sources, and the bodies the adaptations give the
    functions they replace (runtime/replaced, manifest.toml [replaced])."""
    files = sorted((ROOT / "pipeline").rglob("*.py")) + sorted(INCLUDE.rglob("*.hpp")) + sorted((ROOT / "runtime" / "replaced").glob("*.py"))
    return tuple(f.read_bytes() for f in files if "tests" not in f.relative_to(ROOT).parts)


def _compile(src: Path, obj: Path, flags: list[str], cxx: str, std: str) -> None:
    if src.suffix == ".c":                       # a vendored C library: the compiler's C front end, its own standard
        proc = subprocess.run([cxx, *flags, "-x", "c", "-c", str(src), "-o", str(obj)], capture_output=True, text=True, check=False)
    else:
        proc = subprocess.run([cxx, f"-std={std}", *flags, f"-I{INCLUDE}", "-x", "c++", "-c", str(src), "-o", str(obj)],
                              capture_output=True, text=True, check=False)
    if proc.returncode != 0:
        raise RuntimeError(f"{cxx} failed on {src}:\n{proc.stderr[-4000:]}")


class _Lock:
    def __init__(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self.f = open(path, "w")  # noqa: SIM115 -- held for the with-block

    def __enter__(self) -> None:
        fcntl.flock(self.f, fcntl.LOCK_EX)

    def __exit__(self, *exc: object) -> None:
        fcntl.flock(self.f, fcntl.LOCK_UN)
        self.f.close()


def _runtime_key(cxx: str, std: str) -> str:
    """What the runtime library is built from. No fidelity: one library serves an exact build and a lean one."""
    return _key(*(s.read_bytes() for s in [*SOURCES, *INCLUDED, *VENDORED_C, *VENDORED_H]), *(p.read_bytes() for p, _ in PRELUDE),
                *(p.read_bytes() for p in [*NATIVE_IN_PYTHON, *RUNTIME_PYTHON]), *_pipeline_bytes(),
                " ".join([cxx, std, *RUNTIME_FLAGS, *PRELUDE_FLAGS, *VENDORED_FLAGS]).encode())


def runtime_library(cxx: str = CXX, std: str = STD) -> Path:
    out = BUILD / f"runtime-{_runtime_key(cxx, std)}"
    lib = out / "libbella.a"
    with _Lock(BUILD / "runtime.lock"):
        if lib.exists():
            return lib
        out.mkdir(parents=True, exist_ok=True)
        units = [(u, RUNTIME_FLAGS) for u in SOURCES] + [(u, VENDORED_FLAGS) for u in VENDORED_C]
        for p in [*(p for p, _ in PRELUDE), *NATIVE_IN_PYTHON, *RUNTIME_PYTHON]:
            cpp = out / f"prelude_{p.stem}.cpp"
            cpp.write_text(to_cpp(p.read_text(encoding="utf-8"), f"<bella prelude {p.name}>", f"bella::prelude_{p.stem.lstrip('_')}", prelude=True),
                           encoding="utf-8")
            units.append((cpp, PRELUDE_FLAGS))
        objs = [out / f"{u.stem}{'.c' if u.suffix == '.c' else ''}.o" for u, _ in units]   # zlib's crc32.c beside the runtime's units
        with ThreadPoolExecutor(max(1, int(os.environ.get("BELLA_JOBS") or os.cpu_count() or 1))) as pool:
            list(pool.map(lambda uo: _compile(uo[0][0], uo[1], uo[0][1], cxx, std), zip(units, objs, strict=True)))
        subprocess.run(["ar", "rcs", str(lib) + ".tmp", *map(str, objs)], check=True)
        os.replace(str(lib) + ".tmp", lib)
    return lib


# ---- staged texts (docs/staging.md): what the dry runs recorded, compiled into the program ----
# A program's own text runs only if the dry run saw it, and the dry run runs its module body: a program that cannot
# have one is spared that. What a dry run of it fails on is the program's own to say, when it runs. typing compiles a
# string forward reference when it makes one (a TypeVar's bound, Optional["Node"], types.UnionType[int, "Node"], a TypedDict's
# fields): a name typing exports, or UnionType, subscripted with a string, may stage a compile.
_MAY_STAGE = re.compile(r"\b(?:exec|eval|compile|namedtuple|NamedTuple|dataclass|make_dataclass|TypeVar|ForwardRef|TypedDict)\b"
                        r"|\b(?:" + "|".join(sorted({"UnionType", *(n for n in typing.__all__ if n[0].isupper())})) + r")\[[^\]]*[\"']")   # across lines: a subscription may span several (G16 #2)
_FUTURE_MASK = 0x3FE0000                 # every CO_FUTURE_* flag, as the dry run keys a compile


@dataclass(frozen=True)
class StagedRow:
    site: str
    kind: str
    source: bytes
    is_bytes: bool
    namespace: str | None                # None: it does not lower yet, and `why` says so
    why: str
    text: str
    future: frozenset[str]


@dataclass(frozen=True)
class CompileRow:
    """A staged compile() (docs/staging.md section 4): its key as the dry run made it, and its outcome: the code (a body to
    run, and the code object's names and counts, copied from the one CPython made), or the exception CPython raised and its
    arguments (encoded, `encoded_value`). `why` is the refusal when either cannot be given. Rows whose code objects CPython
    finds equal share a `group`."""
    site: str
    source: bytes
    is_bytes: bool
    filename: str
    mode: str
    flags: int
    optimize: int
    module: str | None
    feature_version: int
    namespace: str | None
    why: str
    text: str
    future: frozenset[str]
    code: tuple[Any, ...] | None         # (co_name, co_qualname, co_firstlineno, co_argcount, co_posonlyargcount,
                                         #  co_kwonlyargcount, co_varnames, co_cellvars, co_freevars, co_flags)
    raises: str | None
    raise_args: bytes
    group: int


def encoded_value(v: object) -> bytes:
    """An exception's argument as the runtime decodes it (runtime/src/staged.cpp, decoded): N None, T/F a bool, i<digits>;
    an int, s<length>:<UTF-8> a str, t<count>; a tuple of what follows. Anything else cannot be given."""
    if v is None:
        return b"N"
    if isinstance(v, bool):
        return b"T" if v else b"F"
    if isinstance(v, int):
        return b"i" + str(v).encode() + b";"
    if isinstance(v, str):
        data = v.encode("utf-8", "surrogatepass")
        return b"s" + str(len(data)).encode() + b":" + data
    if isinstance(v, tuple):
        return b"t" + str(len(v)).encode() + b";" + b"".join(encoded_value(x) for x in v)
    raise TypeError(type(v).__name__)


@cache
def _stdlib_artefact() -> dict[str, Any]:
    from pipeline.staging import run as staging  # noqa: PLC0415  # the dry run's machinery, for the builds that need it
    path = staging.stdlib_artefact(staging.phase1_blocked()).with_suffix(".bin")
    with path.open("rb") as f:
        artefact: dict[str, Any] = marshal.load(f)
    return artefact


def _program_artefact(program: Path) -> dict[str, Any] | None:
    from pipeline.staging import run as staging  # noqa: PLC0415
    try:
        path = staging.program_artefact(program, None, staging.phase1_blocked()).with_suffix(".bin")
    except staging.DryRunFailed as exc:
        if exc.tool:      # the tool's own failure: going on without it would stop the program at a text it has a right to (review F17 #15)
            raise
        return None
    with path.open("rb") as f:
        artefact: dict[str, Any] = marshal.load(f)
    return artefact


def _warned(source: str, filename: str, mode: str, flags: int) -> str:
    """What CPython's compiler warns of in a text (`1 is 1`, an invalid escape sequence), "" when nothing. It issues the warning
    each time the program compiles the text, through the filters of that moment (under "error" the compile raises
    SyntaxError); the runtime replays none, so such a text stops by name (review F17 #11)."""
    with warnings.catch_warnings(record=True) as seen:
        warnings.simplefilter("always")
        try:
            compile(source, filename, mode, flags & _FUTURE_MASK, dont_inherit=True)
        except (SyntaxError, ValueError, OverflowError, RecursionError, MemoryError):
            return ""                            # no code: what the text raises is its row's own matter
    if not seen:
        return ""
    said = "; ".join(f"{w.category.__name__}: {w.message}" for w in seen)
    return f"the staged text makes CPython's compiler warn ({said}), each time the program compiles it; a warning is not replayed yet"


def _reachable(key: tuple[Any, ...]) -> bool:
    """Whether the runtime's compile() can reach this key: a call whose arguments CPython rejects before it compiles (a mode
    it does not know, a module that is not a str, a number beyond a C int) raises there, before any lookup, and the dry
    run's key of it is never matched."""
    _site, _, _source, _filename, mode, flags, optimize, module, feature_version = key
    numbers = (flags, optimize, feature_version)
    return (mode in ("exec", "eval", "single") and (module is None or isinstance(module, str))
            and all(isinstance(n, int) and -(2 ** 31) <= n < 2 ** 31 for n in numbers) and -1 <= optimize <= 2)


def _compile_row(key: tuple[Any, ...], outcome: tuple[Any, ...], groups: dict[Any, int]) -> CompileRow:
    """A staged compile's row: what the runtime matches (the key), and what it answers or why it cannot."""
    site, _, source, filename, mode, flags, optimize, module, feature_version = key
    given = source.encode("utf-8", "surrogatepass") if isinstance(source, str) else source
    future = features(flags)
    text = source_text("exec", source)          # compile() strips nothing (eval() strips its own text's leading blanks)
    why, namespace, code, raises, raise_args, group = "", None, None, None, b"", -1
    if outcome[0] == "raises":
        cls = getattr(builtins, outcome[1], None)
        if not (isinstance(cls, type) and issubclass(cls, BaseException)):
            why = f"E-01: compile at {site} raised {outcome[1]}, which is not a built-in exception"
        else:
            try:
                raises, raise_args = outcome[1], encoded_value(tuple(outcome[2]))
            except TypeError as exc:
                why = f"compile() at {site} raised {outcome[1]} with an argument the build cannot give (a {exc})"
    elif mode not in ("exec", "eval"):
        why = f"compile() at {site} in mode {mode!r} (an interactive statement prints its value)"
    elif flags & ~_FUTURE_MASK:
        why = f"compile() at {site} with flags {flags:#x}, beyond the __future__ features"
    elif optimize not in (-1, 0):
        why = f"compile() at {site} with optimize={optimize} (asserts and docstrings removed)"
    else:
        c = outcome[1]
        namespace = "bella::staged_compile_" + _key(mode.encode(), given, str(filename).encode(), " ".join(sorted(future)).encode())
        warned = _warned(text, str(filename), mode, flags)
        try:
            if warned:
                namespace, why = None, f"compile() at {site}: {warned}"
            else:
                lowered_unit(text, filename, namespace, mode, future)
        except (L.Unsupported, L.DialectError, SyntaxError, wf2.WellFormednessError) as exc:
            namespace, why = None, f"compile() at {site}: the staged text does not lower yet: {type(exc).__name__}: {exc}"
        code = (c.co_name, c.co_qualname, c.co_firstlineno, c.co_argcount, c.co_posonlyargcount, c.co_kwonlyargcount,
                c.co_varnames, c.co_cellvars, c.co_freevars, c.co_flags)
        group = groups.setdefault(c, len(groups))   # code_richcompare: code objects equal by value share a group
    return CompileRow(site, given, isinstance(source, bytes), str(filename), str(mode), flags, optimize, module, feature_version,
                      namespace, why, text, future, code, raises, raise_args, group)


def staged_tables(program: Path, modules: list[ProgramModule],
                  notes: list[str] | None = None) -> tuple[list[StagedRow], dict[str, str], dict[str, str], list[CompileRow]]:
    """The texts of the sites this program has, their compiles, and the sites' own refusals; `notes` takes what the build has
    to say about them (where the program's dry run was ended early)."""
    names = {m.name for m in modules}
    own = [read_source(program), *(read_source(m.path) for m in modules if m.path is not None and not m.frozen and m.origin is None
                                   and not m.path.is_relative_to(STDLIB))]
    # the standard library's artefact holds every module's sites, of which this program has its closure's; its own artefact
    # holds what this program ran, the texts of a text included, whose site is named after the `__name__` of the globals it was
    # given (no module at all)
    artefacts: list[tuple[dict[str, Any], bool]] = [(_stdlib_artefact(), False)] if names else []
    if any(_MAY_STAGE.search(text) for text in own):
        made = _program_artefact(program)
        if made is not None:
            artefacts.append((made, True))
            said = notes if notes is not None else []
            for file, line, what in made["confined"]:     # review F17 #7: the build goes on, and says where the dry run ended
                said.append(f"bella: note: {file}:{line}: the dry run of this module body ended here, at {what}: a module body's "
                             f"effects on the world are not performed at build time. Definition-time code the body reaches after "
                             f"this line is not staged and stops the program by name (docs/staging.md)")
    names |= {"__main__"}
    rows: dict[tuple[str, str, str | bytes], StagedRow] = {}
    compiles: dict[tuple[Any, ...], CompileRow] = {}
    groups: dict[Any, int] = {}
    refused: dict[str, str] = {}
    unstaged: dict[str, str] = {}
    for artefact, whole in artefacts:
        for key, outcome in artefact["compiled"].items():
            if (whole or key[0].partition(":")[0] in names) and key not in compiles and _reachable(key):
                compiles[key] = _compile_row(key, outcome, groups)
        for (site, kind, source), (_code, flags) in artefact["texts"].items():
            if not (whole or site.partition(":")[0] in names) or (site, kind, source) in rows:
                continue
            given = source.encode("utf-8", "surrogatepass") if isinstance(source, str) else source
            future = features(flags)
            text = source_text(kind, source)
            name = "bella::staged_" + _key(kind.encode(), given, " ".join(sorted(future)).encode())
            warned = _warned(text, "<string>", kind, flags)
            if warned:
                rows[(site, kind, source)] = StagedRow(site, kind, given, isinstance(source, bytes), None, warned, text, future)
                continue
            try:
                lowered_unit(text, "<string>", name, kind, future)
                rows[(site, kind, source)] = StagedRow(site, kind, given, isinstance(source, bytes), name, "", text, future)
            except (L.Unsupported, L.DialectError, SyntaxError, wf2.WellFormednessError) as exc:
                rows[(site, kind, source)] = StagedRow(site, kind, given, isinstance(source, bytes), None,
                                                       f"the staged text does not lower yet: {type(exc).__name__}: {exc}", text, future)
        refused.update({s: m for s, m in artefact["refused"].items() if whole or s.partition(":")[0] in names})
        unstaged.update({s: m for s, m in artefact["unstaged"].items() if whole or s.partition(":")[0] in names})
    return list(rows.values()), refused, unstaged, list(compiles.values())


def _compiles_cpp(compiles: list[CompileRow]) -> tuple[str, str]:
    """The staged compiles' code records and table, and the span main() registers."""
    if not compiles:
        return "", "{}"
    def strings(ns: tuple[str, ...]) -> str:
        return "{" + ", ".join(c_string(n) for n in ns) + "}"
    records, items = [], []
    for i, r in enumerate(compiles):
        record = "nullptr"
        if r.code is not None:
            name, qualname, first, argc, posonly, kwonly, varnames, cellvars, freevars, flags = r.code
            records.append(f"static const ::bella::Code STAGED_CODE_{i}{{{c_string(name)}, {c_string(qualname)}, {c_string(r.filename)}, "
                           f"{first}, {argc}, {posonly}, {kwonly}, false, false, {strings(varnames)}, nullptr, true, "
                           f"{strings(cellvars)}, {strings(freevars)}, {flags}}};")
            record = f"&STAGED_CODE_{i}"
        items.append(f"    {{{c_string(r.site)}, {c_bytes(r.source)}, {len(r.source)}, {'true' if r.is_bytes else 'false'}, "
                     f"{c_string(r.filename)}, {c_string(r.mode)}, {r.flags}, {r.optimize}, "
                     f"{c_string(r.module) if r.module is not None else 'nullptr'}, {r.feature_version}, {record}, "
                     f"{'::' + r.namespace + '::module_body' if r.namespace else 'nullptr'}, {c_string(r.why)}, "
                     f"{c_string(r.raises) if r.raises else 'nullptr'}, {c_bytes(r.raise_args)}, {len(r.raise_args)}, {r.group}}}")
    table = "static const ::bella::StagedCompile STAGED_COMPILES[] = {\n" + ",\n".join(items) + "\n};\n"
    return "\n".join(records) + "\n" + table, f"std::span<const ::bella::StagedCompile>(STAGED_COMPILES, {len(compiles)})"


def _staged_cpp(rows: list[StagedRow], refused: dict[str, str], unstaged: dict[str, str], compiles: list[CompileRow]) -> tuple[str, str]:
    """Its declarations and tables, and the line of main() that registers them."""
    if not rows and not refused and not unstaged and not compiles:
        return "", ""
    bodies: list[str | None] = [r.namespace for r in rows] + [c.namespace for c in compiles]
    decls = sorted({f"namespace {n} {{ ::bella::Ref module_body(::bella::Module* m); }}" for n in bodies if n})
    body = [f"    {{{c_string(r.site)}, {c_string(r.kind)}, {c_bytes(r.source)}, {len(r.source)}, {'true' if r.is_bytes else 'false'}, "
            f"{'::' + r.namespace + '::module_body' if r.namespace else 'nullptr'}, {c_string(r.why)}}}" for r in rows]
    compile_tables, compiles_span = _compiles_cpp(compiles)
    def sites(name: str, table: dict[str, str]) -> tuple[str, str]:
        if not table:
            return "", "{}"
        items = ",\n".join(f"    {{{c_string(s)}, {c_string(m)}}}" for s, m in sorted(table.items()))
        return f"static const ::bella::StagedSite {name}[] = {{\n{items}\n}};\n", f"std::span<const ::bella::StagedSite>({name}, {len(table)})"
    refused_table, refused_span = sites("STAGED_REFUSED", refused)
    unstaged_table, unstaged_span = sites("STAGED_UNSTAGED", unstaged)
    texts = "static const ::bella::StagedText STAGED[] = {\n" + ",\n".join(body) + "\n};\n" if rows else ""
    texts_span = f"std::span<const ::bella::StagedText>(STAGED, {len(rows)})" if rows else "{}"
    return ("\n".join(decls) + "\n" + texts + refused_table + unstaged_table + compile_tables,
            f"    ::bella::register_staged({texts_span}, {refused_span}, {unstaged_span}, {compiles_span});\n")


def long_literals(source: bytes) -> list[tuple[int, int, str]]:
    """The decimal integer literals of a main program that a limit of digits could refuse: (digits, line, the line's text)
    for each of more than 640 digits (sys.int_info.str_digits_check_threshold, below which no limit applies), in the order
    of the text. CPython compiles a main program at each start, under the limit the environment gave, and its parser makes
    a SyntaxError of the first literal longer than it (_PyPegen_number_token); a compiled program converted its literals at
    the build, so its start checks these against the limit instead (runtime/src/call.cpp, refuse_long_literal; RL-555, the
    author's decision of 2026-11-20; case C-8-18). The digits are counted without the underscores; a literal of zeros, a
    literal of another base, a float and an imaginary number have no limit."""
    threshold = sys.int_info.str_digits_check_threshold
    # the file tokenizer reads with universal newlines: a carriage return alone ends a line too (RL-570)
    source = source.replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    lines = source.splitlines(keepends=True)
    encoding = "utf-8"
    found: list[tuple[int, int, str]] = []
    for token in tokenize.tokenize(io.BytesIO(source).readline):
        if token.type == tokenize.ENCODING:
            encoding = "utf-8" if token.string == "utf-8-sig" else token.string
        if token.type != tokenize.NUMBER or not re.fullmatch(r"[0-9](?:_?[0-9])*", token.string):
            continue
        digits = sum(c != "_" for c in token.string)
        if digits > threshold and token.string.strip("0_"):
            found.append((digits, token.start[0], _program_text(lines, token.start[0], encoding)))
    return found


def _program_text(lines: list[bytes], lineno: int, encoding: str) -> str:
    """The text of a line as the SyntaxError has it (err_programtext, Python/errors.c): the line is read into a buffer of
    1000, so the first 999 bytes of it and no more (RL-571), without the mark of the byte order on the first line, decoded
    with what does not decode replaced (a character the cut divides)."""
    chunk = lines[lineno - 1][:999]
    if lineno == 1 and chunk.startswith(b"\xef\xbb\xbf"):
        chunk = chunk[3:]
    return chunk.decode(encoding, "replace")


def run_filename(given: str) -> str:
    """The name CPython has for a program started as `python GIVEN` (config_run_filename_abspath, _Py_abspath): the path as
    given when it is absolute, else the current directory, a separator and the path as given. Nothing is normalised, so
    `link/../prog.py` stays what the file system takes it for and `./prog.py` keeps its dot: the main module's __file__,
    the name in its code objects and the file a warning names and reads (RL-606)."""
    return given if os.path.isabs(given) else os.getcwd() + os.sep + given


CompilerWarning = tuple[str, str, int]           # the category's name, the message, the line


def _compiled_once(source: bytes, filename: str) -> tuple[list[CompilerWarning], int | None]:
    """What CPython's compiler warns of when it compiles a text as a main program, in the order it warns, and the line of
    the SyntaxError it stopped at (None: it compiled the text). The host is the pinned interpreter, so the list is CPython's
    own and no rule of the compiler's is written down here a second time."""
    with warnings.catch_warnings(record=True) as seen:
        warnings.simplefilter("always")
        try:
            compile(source, filename, "exec", dont_inherit=True, optimize=0)
            stopped = None
        except SyntaxError as exc:
            stopped = exc.lineno or 0
    return [(w.category.__name__, str(w.message), w.lineno) for w in seen], stopped


def compiler_warnings(source: bytes, filename: str) -> list[CompilerWarning]:
    """The warnings of CPython's compiler for a main program's text: an escape sequence that is none, a number that runs into
    a keyword, `is` with a literal, an assertion of a tuple, a literal called or subscripted. CPython compiles a main program
    at each start and gives them each time, before the program's first statement: the tokenizer's and the parser's in the
    order of the text, then the code generator's (pyrun_file; warn_explicit with the module `__main__` and no registry, so
    each is shown under the filters a program starts with). A compiled program gives the ones noted here at its start
    (runtime/src/call.cpp, as_compiled_at_each_start; RL-572, the author's decision of 2026-11-21; case C-8-19). `return`,
    `break` and `continue` out of a finally block are refused by the build (D-10) and never get here."""
    found, stopped = _compiled_once(source, filename)
    if stopped is not None:
        raise SyntaxError(f"{filename}: CPython's compiler stops at line {stopped} of a text the build took")
    return found


def warned_when_refused(source: bytes, filename: str, literals: list[tuple[int, int, str]]) -> list[list[CompilerWarning]]:
    """For each long literal of long_literals(): what CPython's compiler warns of when its parser refuses that literal under
    a limit of digits, in its order. That is not the start of the whole compile's list: the parser's warnings end where
    the literal is, and CPython then reads the rest of the text with its tokenizer alone, to look for a tokenizer's error
    (_PyPegen_tokenize_full_source_to_check_for_errors), which gives the tokenizer's warnings of the rest and none of the
    parser's or the code generator's (RL-611). So the list is asked of the host, by compiling the text under a limit that
    this literal is the first to pass. A literal no longer than one before it is never the first past a limit: no list."""
    lists: list[list[CompilerWarning]] = []
    limit = sys.int_info.str_digits_check_threshold
    was = sys.get_int_max_str_digits()
    try:
        for digits, line, _text in literals:
            if digits <= limit:
                lists.append([])
                continue
            sys.set_int_max_str_digits(limit)
            found, stopped = _compiled_once(source, filename)
            if stopped != line:
                raise RuntimeError(f"{filename}: under a limit of {limit} digits CPython's compiler was to stop at line {line} "
                                   f"and {'compiled the text' if stopped is None else f'stopped at line {stopped}'}")
            lists.append(found)
            limit = digits
    finally:
        sys.set_int_max_str_digits(was)
    return lists


def main_unit(main_file: Path, modules: list[ProgramModule], staged: tuple[str, str] = ("", ""), annotate: tuple[str, str] = ("", ""),
              syntax_warnings: bool = True, named: str | None = None) -> str:
    """main(): the runtime's start with the prelude, the main module's body, its __file__ (`named`, the name CPython has for
    the program: run_filename; without one the absolute path, a link not followed), sys.path[0] (the directory of the
    file a link leads to), the registry of the modules compiled with it, and the tables of the staged texts and of the annotate
    functions' entry points. `syntax_warnings`: whether the program gives the compiler's warnings of its text at each start
    (the build's switch; without them the table is left out, and that is all the switch does)."""
    named = named if named is not None else os.path.abspath(main_file)
    preludes = "\n".join(f"namespace bella::prelude_{p.stem} {{ ::bella::Ref module_body(::bella::Module* m); }}" for p, _ in PRELUDE)
    bodies = ", ".join(f"{{{c_string(name)}, ::bella::prelude_{p.stem}::module_body}}" for p, name in PRELUDE)
    decls = "\n".join(["namespace bella::m_main { ::bella::Ref module_body(::bella::Module* m); }",
                       *(f"namespace {namespace_of(m.name)} {{ ::bella::Ref module_body(::bella::Module* m); }}"
                         for m in modules if m.path is not None)])
    def entry(m: ProgramModule) -> str:
        kind = "Namespace" if m.path is None else "Frozen" if m.frozen else "Source"
        file = m.origin or m.path
        body = "nullptr" if m.path is None else f"::{namespace_of(m.name)}::module_body"
        return (f"    {{{c_string(m.name)}, {body}, {c_string(str(file) if file is not None else '')}, "
                f"{'true' if m.package else 'false'}, ::bella::ModuleKind::{kind}}}")
    known = {m.name for m in modules}
    rows = [entry(m) for m in modules]
    rows += [f"    {{{c_string(n)}, nullptr, \"\", false, ::bella::ModuleKind::Omitted}}" for n in sorted(omitted_modules() - known)]
    # CPython finds these whatever the program's files say; one the build does not compile is refused
    rows += [f"    {{{c_string(n)}, nullptr, \"\", false, ::bella::ModuleKind::Refused}}" for n in sorted(FROZEN - known - omitted_modules())]
    entries = ",\n".join(rows)
    table = f"static const ::bella::ModuleEntry MODULES[] = {{\n{entries}\n}};\n"
    count = len(rows)
    main_text = main_file.read_bytes()
    literals = long_literals(main_text)
    warned = compiler_warnings(main_text, named) if syntax_warnings else []
    refused = warned_when_refused(main_text, named, literals) if warned and literals else [[] for _ in literals]

    def warning_rows(given: list[CompilerWarning]) -> str:
        return ",\n".join(f"    {{{c_string(category)}, {c_string(message)}, {line}}}" for category, message, line in given)
    literal_table = literal_call = ""
    if warned:
        literal_table += f"static const ::bella::CompilerWarning COMPILER_WARNINGS[] = {{\n{warning_rows(warned)}\n}};\n"
        literal_call += f"    ::bella::set_compiler_warnings(std::span<const ::bella::CompilerWarning>(COMPILER_WARNINGS, {len(warned)}));\n"
    if literals:
        every = [one for given in refused for one in given]
        if every:                                # one table for all of them, each literal's own a stretch of it
            literal_table += f"static const ::bella::CompilerWarning REFUSED_WARNINGS[] = {{\n{warning_rows(every)}\n}};\n"
        literal_rows, at = [], 0
        for (digits, line, text), given in zip(literals, refused, strict=True):
            where = f"REFUSED_WARNINGS + {at}" if given else "nullptr"
            literal_rows.append(f"    {{{digits}, {line}, {c_string(text)}, {where}, {len(given)}}}")
            at += len(given)
        literal_table += "static const ::bella::LongLiteral LONG_LITERALS[] = {\n" + ",\n".join(literal_rows) + "\n};\n"
        literal_call += f"    ::bella::set_long_literals(std::span<const ::bella::LongLiteral>(LONG_LITERALS, {len(literals)}));\n"
    return ('// The main unit, compiled by Bella: the start, and the modules compiled with the program.\n'
            '#include "bella/runtime.hpp"\n\n' + decls + "\n" + preludes + "\n\n" + table + literal_table + staged[0] + annotate[0] +
            "\nint main(int argc, char** argv) {\n" + staged[1] + annotate[1] + literal_call +
            f"    ::bella::set_stdlib_dir({c_string(getattr(sys, '_stdlib_dir', None) or str(STDLIB))});\n" +
            "    ::bella::set_lean(BELLA_IS_LEAN);\n" +      # the header's, 1 under -DBELLA_LEAN and 0 without: one text for both builds
            f"    return ::bella::run_main(argc, argv, ::bella::m_main::module_body, {c_string(named)},\n"
            f"                             {c_string(str(main_file.resolve().parent))}, {{{bodies}}},\n"
            f"                             std::span<const ::bella::ModuleEntry>(MODULES, {count}));\n}}\n")


def _unit_flags(flags: list[str], fidelity: str) -> list[str]:
    """The flags of a unit build() compiles: a lean build's carry the define, an exact build's are the flags as they
    were. They are part of the unit's key (_object_key), so the two builds never share an object."""
    return [*flags, LEAN_DEFINE] if fidelity == "lean" else flags


def _object_key(cpp: str, cxx: str, std: str, flags: list[str]) -> str:
    return _key(cpp.encode(), *(h.read_bytes() for h in sorted(INCLUDE.rglob("*.hpp"))), " ".join([cxx, std, *flags]).encode())


def _object(cpp: str, name: str, cxx: str, std: str, flags: list[str] = PROGRAM_FLAGS) -> Path:
    """A unit compiled once per content: its object file under build/compiled/units, kept across
    changes to the runtime's sources, since it depends only on its text, the headers and the flags."""
    key = _object_key(cpp, cxx, std, flags)
    obj = BUILD / "units" / f"{name}-{key}.o"
    if obj.exists():
        return obj
    obj.parent.mkdir(parents=True, exist_ok=True)
    # parallel builds compile the same unit: each from a file of its own, or one reads another's half
    src = obj.with_name(f"{obj.stem}.{os.getpid()}.cpp")
    src.write_text(cpp, encoding="utf-8")
    tmp = obj.with_name(obj.name + f".{os.getpid()}.tmp")
    _compile(src, tmp, flags, cxx, std)
    os.replace(tmp, obj)
    src.unlink()
    return obj


def build(program: Path, filename: str, cxx: str = CXX, std: str = STD, keep: Path | None = None, notes: bool = True, *,
          fidelity: str = "exact", syntax_warnings: bool = True, main_file: str | None = None) -> Path:
    """The program's binary; `keep`: also write the main module's C++ there (the committed examples). `fidelity`: "exact"
    or "lean" (FIDELITIES); `syntax_warnings`: whether the program gives the compiler's warnings of its text at each start
    (D-29 when not); `main_file`: the main module's __file__ (run_filename() of what the program was started as; without
    one the program's absolute path). The environment is not asked here, so a caller gets the build it names."""
    if fidelity not in FIDELITIES:
        raise ValueError(f"fidelity {fidelity!r}: a build is {' or '.join(FIDELITIES)}")
    # The host's compiler warns each time the build parses or compiles a text of the program's, several times a text. What
    # the program is to say of its own text is noted once (compiler_warnings), and what the build says of it is said once
    # below; the rest is not the build's to print, least of all under --run, whose streams are the program's own
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", SyntaxWarning)
        return _build(program, filename, cxx, std, keep, notes, fidelity, syntax_warnings,
                      main_file if main_file is not None else os.path.abspath(program))


def _say_compiler_warnings(shown: str, path: Path, found: list[CompilerWarning]) -> None:
    """The build's own note, on its standard error: what CPython's compiler warns of in one text of the program's, each
    warning once, in CPython's two lines. The line under it is read by the host, as the text was."""
    try:
        lines = read_source(path).split("\n")
    except SyntaxError:                          # a text whose encoding is refused: its warnings, if it had any, without their lines
        lines = []
    for category, message, line in found:
        print(f"{shown}:{line}: {category}: {message}", file=sys.stderr)
        if 0 < line <= len(lines) and lines[line - 1].strip():
            print(f"  {lines[line - 1].strip()}", file=sys.stderr)


def _build(program: Path, filename: str, cxx: str, std: str, keep: Path | None, notes: bool, fidelity: str, syntax_warnings: bool,
           main_file: str) -> Path:
    lib = runtime_library(cxx, std)              # the same library for both
    # A main program whose text CPython's compiler warns of has `warnings` imported for it at each start, before its first
    # statement (call_show_warning): the program holds the module then, as if its text had asked (a text CPython's compiler
    # stops at is refused further down, by the passes or by main_unit). A build that only builds says them here, before
    # anything can refuse the text: the warnings CPython's compiler gave until its own error are said too (RL-601)
    found = _compiled_once(program.read_bytes(), main_file)[0]
    if notes:
        _say_compiler_warnings(main_file, program, found)
    warns = syntax_warnings and bool(found)
    modules = find_program_modules(program, ("warnings",) if warns else ())
    main_source = read_source(program)
    main_cpp = to_cpp(main_source, filename, "bella::m_main")
    if keep is not None:
        keep.parent.mkdir(parents=True, exist_ok=True)
        keep.write_text(main_cpp, encoding="utf-8")
    units = [(main_cpp, program.stem, PROGRAM_FLAGS)]
    entry_rows: list[EntryRow] = []

    def entry_points(source: str, shown: str, namespace: str, name: str, flags: list[str]) -> None:
        rows, cpp = annotate_entries(source, shown, "bella::annotate_" + namespace.removeprefix("bella::"))
        entry_rows.extend(rows)
        if cpp is not None:
            units.append((cpp, f"{name}-annotate", flags))
    entry_points(main_source, filename, "bella::m_main", program.stem, PROGRAM_FLAGS)
    for m in modules:
        if m.path is not None:
            # a frozen module's code says `<frozen os>`, as CPython's does
            shown = f"<frozen {m.name}>" if m.frozen else str(m.origin or m.path)
            library = m.frozen or m.origin is not None or m.path.is_relative_to(STDLIB)
            source = read_source(m.path)
            units.append((lowered_unit(source, shown, namespace_of(m.name), looks=m.name not in LOOK_FREE), m.name,
                          LIBRARY_FLAGS if library else PROGRAM_FLAGS))
            entry_points(source, shown, namespace_of(m.name), m.name, LIBRARY_FLAGS if library else PROGRAM_FLAGS)
    said: list[str] = []
    rows, refused, unstaged, compiles = staged_tables(program, modules, said)
    for line in said if notes else ():           # not under --run, whose streams are the program's own
        print(line, file=sys.stderr)
    for m in modules if notes else ():           # and those of the program's other modules (not the standard library's), as found
        if m.path is not None and not (m.frozen or m.origin is not None or m.path.is_relative_to(STDLIB)):
            _say_compiler_warnings(str(m.path), m.path, _compiled_once(m.path.read_bytes(), str(m.path))[0])
    for name in sorted({r.namespace for r in rows if r.namespace}):
        row = next(r for r in rows if r.namespace == name)
        units.append((lowered_unit(row.text, "<string>", name, row.kind, row.future), name.rpartition("::")[2], LIBRARY_FLAGS))
    for name in sorted({r.namespace for r in compiles if r.namespace}):
        made = next(r for r in compiles if r.namespace == name)
        units.append((lowered_unit(made.text, made.filename, name, made.mode, made.future), name.rpartition("::")[2], LIBRARY_FLAGS))
    units.append((main_unit(program, modules, _staged_cpp(rows, refused, unstaged, compiles), _entries_cpp(entry_rows), syntax_warnings,
                            main_file), f"{program.stem}-main", PROGRAM_FLAGS))
    with ThreadPoolExecutor(max(1, int(os.environ.get("BELLA_JOBS") or os.cpu_count() or 1))) as pool:
        objs = list(pool.map(lambda u: _object(u[0], u[1], cxx, std, _unit_flags(u[2], fidelity)), units))
    # the runtime's debug information is most of a binary, and every program would carry a copy
    strip = [] if os.environ.get("BELLA_KEEP_DEBUG") else ["-Wl,--strip-debug"]
    out = BUILD / f"{program.stem}-{_link_key(objs, lib, strip, fidelity)}"
    exe = out / program.stem
    if exe.exists():
        _forget_previous(program, out, fidelity, syntax_warnings)   # this build's binary too, though another made it (RL-609)
        return exe
    out.mkdir(parents=True, exist_ok=True)
    tmp = str(exe) + f".{os.getpid()}.tmp"
    proc = subprocess.run([cxx, f"-std={std}", *PROGRAM_FLAGS, *strip, *map(str, objs), str(lib), "-o", tmp],
                          capture_output=True, text=True, check=False)
    if proc.returncode != 0:
        raise RuntimeError(f"{cxx} failed linking {program}:\n{proc.stderr[-4000:]}")
    os.replace(tmp, exe)
    _forget_previous(program, out, fidelity, syntax_warnings)
    return exe


def _link_key(objs: list[Path], lib: Path, strip: list[str], fidelity: str) -> str:
    """A binary's key: its objects and its library by their names, which hold their keys, and how it is linked. A lean
    build's objects differ from an exact one's already, by their flags; the fidelity is named as well, so that the two
    binaries of one program are two by what this says and not by that reasoning."""
    return _key(*(o.name.encode() for o in objs), lib.parent.name.encode(), " ".join(strip).encode(), fidelity.encode())


def _pointer(program: Path, fidelity: str, syntax_warnings: bool = True) -> Path:
    """Where a program's current binary is noted, one note per fidelity and per --syntax-warnings: built each way, a
    program keeps each binary. The note of an exact build that warns is where it was before there was a choice, so the
    binary a program had is still replaced."""
    return BUILD / "last" / _key(str(program.resolve()).encode(), *([] if fidelity == "exact" else [fidelity.encode()]),
                                 *([] if syntax_warnings else [b"syntax-warnings=off"]))


def _forget_previous(program: Path, current: Path, fidelity: str = "exact", syntax_warnings: bool = True) -> None:
    """A program rebuilt replaces its previous binary of the same kind: each change to the runtime would otherwise
    leave one more copy of every program under build/compiled. The previous one stays while another kind's note still
    names it: a program with nothing to warn of is one binary with and without --syntax-warnings (RL-609)."""
    pointer = _pointer(program, fidelity, syntax_warnings)
    pointer.parent.mkdir(parents=True, exist_ok=True)
    previous = pointer.read_text(encoding="utf-8") if pointer.exists() else ""
    pointer.write_text(current.name, encoding="utf-8")
    if previous and previous != current.name:
        others = (_pointer(program, f, w) for f in FIDELITIES for w in (True, False))
        if not any(other != pointer and other.exists() and other.read_text(encoding="utf-8") == previous for other in others):
            shutil.rmtree(BUILD / previous, ignore_errors=True)


OPTIONS = ("--fidelity", "--syntax-warnings")


def _options(argv: list[str], leading: bool) -> tuple[dict[str, str], list[str]]:
    """`--fidelity=WHICH` or `--fidelity WHICH`, and `--syntax-warnings` likewise, taken out of the arguments, and the
    arguments without them; the last one given of each counts. `leading`: only ahead of the first other argument (under
    --run, what follows the program is the program's own); otherwise anywhere, as -o is."""
    chosen: dict[str, str] = {}
    kept: list[str] = []
    i = 0
    while i < len(argv):
        name, equals, value = argv[i].partition("=")
        if name in OPTIONS and equals:
            chosen[name], i = value, i + 1
        elif argv[i] in OPTIONS:
            chosen[argv[i]], i = (argv[i + 1] if i + 1 < len(argv) else ""), i + 2
        elif leading:
            break
        else:
            kept.append(argv[i])
            i += 1
    return chosen, kept + argv[i:]


def main(argv: list[str]) -> int:
    options, argv = _options(argv, leading=True)                 # ahead of --run
    run = argv[:1] == ["--run"]
    if run:
        argv = argv[1:]
    late, argv = _options(argv, leading=run)                     # after --run; anywhere when the command only builds
    options |= late
    chosen = options.get("--fidelity")
    out_path = None
    if not run and "-o" in argv:
        i = argv.index("-o")
        out_path = Path(argv[i + 1])
        argv = argv[:i] + argv[i + 2:]
    if not argv:
        print(__doc__, file=sys.stderr)
        return 2
    # the option, else the environment (an empty value is no value, as BELLA_JOBS reads its own), else exact. A value that
    # is neither stops here: falling back to exact would run the wrong build under the right name
    fidelity = chosen if chosen is not None else os.environ.get("BELLA_FIDELITY") or "exact"
    if fidelity not in FIDELITIES:
        print(f"bella: {'--fidelity' if chosen is not None else 'BELLA_FIDELITY'} is {fidelity!r}: a build is {' or '.join(FIDELITIES)}",
              file=sys.stderr)
        return 2
    # the same for the compiler's warnings at each start: on unless the option or the environment says off
    said = options.get("--syntax-warnings")
    warns = said if said is not None else os.environ.get("BELLA_SYNTAX_WARNINGS") or "on"
    if warns not in SYNTAX_WARNINGS:
        print(f"bella: {'--syntax-warnings' if said is not None else 'BELLA_SYNTAX_WARNINGS'} is {warns!r}: it is "
              f"{' or '.join(SYNTAX_WARNINGS)}", file=sys.stderr)
        return 2
    program = Path(argv[0])
    named = run_filename(argv[0])                # __file__ and co_filename: the path made absolute as CPython 3.15 makes it
    try:
        exe = build(program, named, notes=not run, fidelity=fidelity, syntax_warnings=warns == "on", main_file=named)
    except (Unsupported, SyntaxError) as exc:
        print(f"bella: refused: {exc}", file=sys.stderr)
        return REFUSED
    if out_path is not None:
        out_path.write_bytes(exe.read_bytes())
        out_path.chmod(0o755)
        exe = out_path
    if not run:
        print(exe)
        return 0
    sys.stdout.flush()
    os.execv(exe, [argv[0], *argv[1:]])


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
