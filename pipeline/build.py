#!/usr/bin/env python3
"""bella build: a program through L2 into C++26, compiled and linked against the runtime.

    python3 pipeline/build.py PROGRAM.py [-o BINARY]           build; print the binary's path
    python3 pipeline/build.py --run PROGRAM.py [ARGS...]        build, then run it as the program

The program is lowered (frontend, to-anf, lifetimes, wf2) and emitted by pipeline/backend/cpp.py;
the runtime library is runtime/src/*.cpp and the prelude (runtime/prelude/*.py, compiled the
same way), built once per content hash under build/compiled/ and shared by every program. Each
module of the program's own that an import can reach (pipeline/closed_world.py) is a unit of its
own, compiled once per content hash; the main unit hands the runtime their registry (spec
section 8). A construct the pipeline refuses stops the build with exit 70, as the evaluators
refuse.
"""
from __future__ import annotations

import fcntl
import hashlib
import marshal
import os
import re
import shutil
import subprocess
import sys
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

REFUSED = 70
BUILD = ROOT / "build" / "compiled"
INCLUDE = ROOT / "runtime" / "include"
SOURCES = sorted((ROOT / "runtime" / "src").glob("*.cpp"))
INCLUDED = sorted((ROOT / "runtime" / "src").glob("*.inc"))       # generated tables the sources include
# the prelude's modules, in this order, each run as the module it names (runtime/src/call.cpp, run_main)
PRELUDE = [(ROOT / "runtime" / "prelude" / "build_class.py", "builtins"), (ROOT / "runtime" / "prelude" / "builtins.py", "builtins"),
           (ROOT / "runtime" / "prelude" / "iterating.py", "builtins"), (ROOT / "runtime" / "prelude" / "templatelib.py", "builtins"),
           (ROOT / "runtime" / "prelude" / "bootstrap.py", "_frozen_importlib")]
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
                    ROOT / "runtime" / "prelude" / "_math_integer.py", ROOT / "runtime" / "prelude" / "math.py",
                    ROOT / "runtime" / "prelude" / "_md5.py", ROOT / "runtime" / "prelude" / "_sha1.py", ROOT / "runtime" / "prelude" / "_sha2.py",
                    ROOT / "runtime" / "prelude" / "_sha3.py", ROOT / "runtime" / "prelude" / "_blake2.py", ROOT / "runtime" / "prelude" / "_hmac.py",
                    ROOT / "runtime" / "prelude" / "_csv.py", ROOT / "runtime" / "prelude" / "_contextvars.py",
                    ROOT / "runtime" / "prelude" / "_bisect.py"]
CXX = os.environ.get("CXX", "g++")
STD = os.environ.get("CXXSTD", "c++26")
# -ffp-contract=off: a*b + c is two operations with two roundings, as the reference computes it. A compiler that
# may fuse them gives -0.0 + 0.0 another sign and rounds a subnormal differently (the runner's g++ did, in complex
# division; -mfma reproduces it): the program's numbers must not depend on what the compiler's target has.
FP_FLAGS = ["-ffp-contract=off"]
RUNTIME_FLAGS = ["-O2", "-g", "-Wall", "-Wextra", *FP_FLAGS]
# -fno-tree-pta: GCC 16's -O1 is super-linear on a long function full of temporaries with destructors.
# A 3143-line module body took over 25 minutes and 24 MB; without the analysis, 15 seconds and 1.2 MB,
# with no measurable cost at run time (fib and an object, dict and exception workload, within noise).
PROGRAM_FLAGS = ["-O1", "-w", "-fno-tree-pta", *FP_FLAGS]
PRELUDE_FLAGS = ["-O1", "-g", "-fno-tree-pta", *FP_FLAGS]     # the prelude's units are lowered Python, the program's kind of code: -O2 takes GCC 16
#                                                               nine minutes on _io.py's unit alone, -O1 under a minute
LIBRARY_FLAGS = ["-O0", "-w", *FP_FLAGS]      # the standard library's units: a fifth of the compile time; speed is not a goal yet


def to_cpp(source: str, filename: str, namespace: str, prelude: bool = False, mode: str = "exec",
           future: frozenset[str] = frozenset()) -> str:
    module: G.Module = lifetimes(to_l2(lower(source, filename, mode=mode, inherit_future=future)))
    wf2.check(module, lifetimes=True)
    return emit_module(module, namespace, filename, prelude)


def lowered_unit(source: str, filename: str, namespace: str, mode: str = "exec", future: frozenset[str] = frozenset()) -> str:
    """to_cpp, kept under build/compiled/lowered by what decides its text: a closure's modules are
    the same for every program that imports them, and lowering them takes seconds each time. The
    compiler's macros are part of it: they decide which names the emitter escapes."""
    key = _key(source.encode(), filename.encode(), namespace.encode(), mode.encode(), " ".join(sorted(future)).encode(), *_pipeline_bytes(),
               " ".join(sorted(header_macros())).encode())
    kept = BUILD / "lowered" / f"{namespace.replace('::', '_')}-{key}.cpp"
    if kept.exists():
        return kept.read_text(encoding="utf-8")
    text = to_cpp(source, filename, namespace, mode=mode, future=future)
    kept.parent.mkdir(parents=True, exist_ok=True)
    tmp = kept.with_name(kept.name + f".{os.getpid()}.tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, kept)
    return text


def _key(*parts: bytes) -> str:
    h = hashlib.sha256()
    for p in parts:
        h.update(hashlib.sha256(p).digest())
    return h.hexdigest()[:16]


@cache
def _pipeline_bytes() -> tuple[bytes, ...]:
    """Everything that decides what a program compiles to: the compiler's own sources."""
    files = sorted((ROOT / "pipeline").rglob("*.py")) + sorted(INCLUDE.rglob("*.hpp"))
    return tuple(f.read_bytes() for f in files if "tests" not in f.relative_to(ROOT).parts)


def _compile(src: Path, obj: Path, flags: list[str], cxx: str, std: str) -> None:
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


def runtime_library(cxx: str = CXX, std: str = STD) -> Path:
    key = _key(*(s.read_bytes() for s in [*SOURCES, *INCLUDED]), *(p.read_bytes() for p, _ in PRELUDE),
               *(p.read_bytes() for p in NATIVE_IN_PYTHON), *_pipeline_bytes(),
               " ".join([cxx, std, *RUNTIME_FLAGS, *PRELUDE_FLAGS]).encode())
    out = BUILD / f"runtime-{key}"
    lib = out / "libbella.a"
    with _Lock(BUILD / "runtime.lock"):
        if lib.exists():
            return lib
        out.mkdir(parents=True, exist_ok=True)
        units = [(u, RUNTIME_FLAGS) for u in SOURCES]
        for p in [*(p for p, _ in PRELUDE), *NATIVE_IN_PYTHON]:
            cpp = out / f"prelude_{p.stem}.cpp"
            cpp.write_text(to_cpp(p.read_text(encoding="utf-8"), f"<bella prelude {p.name}>", f"bella::prelude_{p.stem.lstrip('_')}", prelude=True),
                           encoding="utf-8")
            units.append((cpp, PRELUDE_FLAGS))
        objs = [out / f"{u.stem}.o" for u, _ in units]
        with ThreadPoolExecutor(max(1, int(os.environ.get("BELLA_JOBS") or os.cpu_count() or 1))) as pool:
            list(pool.map(lambda uo: _compile(uo[0][0], uo[1], uo[0][1], cxx, std), zip(units, objs, strict=True)))
        subprocess.run(["ar", "rcs", str(lib) + ".tmp", *map(str, objs)], check=True)
        os.replace(str(lib) + ".tmp", lib)
    return lib


# ---- staged texts (docs/staging.md): what the dry runs recorded, compiled into the program ----
# A program's own text runs only if the dry run saw it, and the dry run runs its module body: a program that cannot
# have one is spared that. What a dry run of it fails on is the program's own to say, when it runs.
_MAY_STAGE = re.compile(r"\b(?:exec|eval|compile|namedtuple|NamedTuple|dataclass|make_dataclass)\b")


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
    except SystemExit:
        return None
    with path.open("rb") as f:
        artefact: dict[str, Any] = marshal.load(f)
    return artefact


def staged_tables(program: Path, modules: list[ProgramModule]) -> tuple[list[StagedRow], dict[str, str], dict[str, str]]:
    """The texts of the sites this program has, and the sites' own refusals."""
    names = {m.name for m in modules}
    own = [read_source(program), *(read_source(m.path) for m in modules if m.path is not None and not m.frozen and m.origin is None
                                   and not m.path.is_relative_to(STDLIB))]
    artefacts = [_stdlib_artefact()] if names else []
    if any(_MAY_STAGE.search(text) for text in own):
        made = _program_artefact(program)
        if made is not None:
            artefacts.append(made)
    names |= {"__main__"}
    rows: dict[tuple[str, str, str | bytes], StagedRow] = {}
    refused: dict[str, str] = {}
    unstaged: dict[str, str] = {}
    for artefact in artefacts:
        for (site, kind, source), (_code, flags) in artefact["texts"].items():
            if site.partition(":")[0] not in names or (site, kind, source) in rows:
                continue
            given = source.encode("utf-8", "surrogatepass") if isinstance(source, str) else source
            future = features(flags)
            text = source_text(kind, source)
            name = "bella::staged_" + _key(kind.encode(), given, " ".join(sorted(future)).encode())
            try:
                lowered_unit(text, "<string>", name, kind, future)
                rows[(site, kind, source)] = StagedRow(site, kind, given, isinstance(source, bytes), name, "", text, future)
            except (L.Unsupported, L.DialectError, SyntaxError, wf2.WellFormednessError) as exc:
                rows[(site, kind, source)] = StagedRow(site, kind, given, isinstance(source, bytes), None, f"{type(exc).__name__}: {exc}", text, future)
        refused.update({s: m for s, m in artefact["refused"].items() if s.partition(":")[0] in names})
        unstaged.update({s: m for s, m in artefact["unstaged"].items() if s.partition(":")[0] in names})
    return list(rows.values()), refused, unstaged


def _staged_cpp(rows: list[StagedRow], refused: dict[str, str], unstaged: dict[str, str]) -> tuple[str, str]:
    """Its declarations and tables, and the line of main() that registers them."""
    if not rows and not refused and not unstaged:
        return "", ""
    decls = sorted({f"namespace {r.namespace} {{ ::bella::Ref module_body(::bella::Module* m); }}" for r in rows if r.namespace})
    body = [f"    {{{c_string(r.site)}, {c_string(r.kind)}, {c_bytes(r.source)}, {len(r.source)}, {'true' if r.is_bytes else 'false'}, "
            f"{'::' + r.namespace + '::module_body' if r.namespace else 'nullptr'}, {c_string(r.why)}}}" for r in rows]
    def sites(name: str, table: dict[str, str]) -> tuple[str, str]:
        if not table:
            return "", "{}"
        items = ",\n".join(f"    {{{c_string(s)}, {c_string(m)}}}" for s, m in sorted(table.items()))
        return f"static const ::bella::StagedSite {name}[] = {{\n{items}\n}};\n", f"std::span<const ::bella::StagedSite>({name}, {len(table)})"
    refused_table, refused_span = sites("STAGED_REFUSED", refused)
    unstaged_table, unstaged_span = sites("STAGED_UNSTAGED", unstaged)
    texts = "static const ::bella::StagedText STAGED[] = {\n" + ",\n".join(body) + "\n};\n" if rows else ""
    texts_span = f"std::span<const ::bella::StagedText>(STAGED, {len(rows)})" if rows else "{}"
    return ("\n".join(decls) + "\n" + texts + refused_table + unstaged_table,
            f"    ::bella::register_staged({texts_span}, {refused_span}, {unstaged_span});\n")


def main_unit(main_file: Path, modules: list[ProgramModule], staged: tuple[str, str] = ("", "")) -> str:
    """main(): the runtime's start with the prelude, the main module's body, its __file__ (the
    absolute path, a link not followed, as CPython keeps it), sys.path[0] (the directory of the
    file a link leads to), and the registry of the modules compiled with it."""
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
    return ('// The main unit, compiled by Bella: the start, and the modules compiled with the program.\n'
            '#include "bella/runtime.hpp"\n\n' + decls + "\n" + preludes + "\n\n" + table + staged[0] +
            "\nint main(int argc, char** argv) {\n" + staged[1] +
            f"    return ::bella::run_main(argc, argv, ::bella::m_main::module_body, {c_string(os.path.abspath(main_file))},\n"
            f"                             {c_string(str(main_file.resolve().parent))}, {{{bodies}}},\n"
            f"                             std::span<const ::bella::ModuleEntry>(MODULES, {count}));\n}}\n")


def _object(cpp: str, name: str, cxx: str, std: str, flags: list[str] = PROGRAM_FLAGS) -> Path:
    """A unit compiled once per content: its object file under build/compiled/units, kept across
    changes to the runtime's sources, since it depends only on its text, the headers and the flags."""
    key = _key(cpp.encode(), *(h.read_bytes() for h in sorted(INCLUDE.rglob("*.hpp"))), " ".join([cxx, std, *flags]).encode())
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


def build(program: Path, filename: str, cxx: str = CXX, std: str = STD, keep: Path | None = None) -> Path:
    """The program's binary; `keep`: also write the main module's C++ there (the committed examples)."""
    lib = runtime_library(cxx, std)
    modules = find_program_modules(program)
    main_cpp = to_cpp(read_source(program), filename, "bella::m_main")
    if keep is not None:
        keep.parent.mkdir(parents=True, exist_ok=True)
        keep.write_text(main_cpp, encoding="utf-8")
    units = [(main_cpp, program.stem, PROGRAM_FLAGS)]
    for m in modules:
        if m.path is not None:
            # a frozen module's code says `<frozen os>`, as CPython's does
            shown = f"<frozen {m.name}>" if m.frozen else str(m.origin or m.path)
            library = m.frozen or m.origin is not None or m.path.is_relative_to(STDLIB)
            units.append((lowered_unit(read_source(m.path), shown, namespace_of(m.name)), m.name, LIBRARY_FLAGS if library else PROGRAM_FLAGS))
    rows, refused, unstaged = staged_tables(program, modules)
    for name in sorted({r.namespace for r in rows if r.namespace}):
        row = next(r for r in rows if r.namespace == name)
        units.append((lowered_unit(row.text, "<string>", name, row.kind, row.future), name.rpartition("::")[2], LIBRARY_FLAGS))
    units.append((main_unit(program, modules, _staged_cpp(rows, refused, unstaged)), f"{program.stem}-main", PROGRAM_FLAGS))
    with ThreadPoolExecutor(max(1, int(os.environ.get("BELLA_JOBS") or os.cpu_count() or 1))) as pool:
        objs = list(pool.map(lambda u: _object(u[0], u[1], cxx, std, u[2]), units))
    # the runtime's debug information is most of a binary, and every program would carry a copy
    strip = [] if os.environ.get("BELLA_KEEP_DEBUG") else ["-Wl,--strip-debug"]
    key = _key(*(o.name.encode() for o in objs), lib.parent.name.encode(), " ".join(strip).encode())
    out = BUILD / f"{program.stem}-{key}"
    exe = out / program.stem
    if exe.exists():
        return exe
    out.mkdir(parents=True, exist_ok=True)
    tmp = str(exe) + f".{os.getpid()}.tmp"
    proc = subprocess.run([cxx, f"-std={std}", *PROGRAM_FLAGS, *strip, *map(str, objs), str(lib), "-o", tmp],
                          capture_output=True, text=True, check=False)
    if proc.returncode != 0:
        raise RuntimeError(f"{cxx} failed linking {program}:\n{proc.stderr[-4000:]}")
    os.replace(tmp, exe)
    _forget_previous(program, out)
    return exe


def _forget_previous(program: Path, current: Path) -> None:
    """A program rebuilt replaces its previous binary: each change to the runtime would otherwise
    leave one more copy of every program under build/compiled."""
    pointer = BUILD / "last" / _key(str(program.resolve()).encode())
    pointer.parent.mkdir(parents=True, exist_ok=True)
    previous = pointer.read_text(encoding="utf-8") if pointer.exists() else ""
    if previous and previous != current.name:
        shutil.rmtree(BUILD / previous, ignore_errors=True)
    pointer.write_text(current.name, encoding="utf-8")


def main(argv: list[str]) -> int:
    run = argv[:1] == ["--run"]
    if run:
        argv = argv[1:]
    out_path = None
    if not run and "-o" in argv:
        i = argv.index("-o")
        out_path = Path(argv[i + 1])
        argv = argv[:i] + argv[i + 2:]
    if not argv:
        print(__doc__, file=sys.stderr)
        return 2
    program = Path(argv[0])
    try:
        exe = build(program, os.path.abspath(argv[0]))       # co_filename: the absolute path, as CPython 3.15 has it
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
