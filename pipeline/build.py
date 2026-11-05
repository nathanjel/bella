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
import os
import shutil
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from functools import cache
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from pipeline.backend.cpp import c_string, emit_module, header_macros  # noqa: E402
from pipeline.closed_world import FROZEN, STDLIB, ProgramModule, find_program_modules, namespace_of, omitted_modules, read_source  # noqa: E402
from pipeline.l1.frontend import lower  # noqa: E402
from pipeline.l1.grammar import Unsupported  # noqa: E402
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
           (ROOT / "runtime" / "prelude" / "iterating.py", "builtins"),
           (ROOT / "runtime" / "prelude" / "bootstrap.py", "_frozen_importlib")]
# built-in modules CPython writes in C and this runtime in Python: compiled with the prelude, run at the
# first import (runtime/src/imports.cpp)
NATIVE_IN_PYTHON = [ROOT / "runtime" / "prelude" / "itertools.py"]
CXX = os.environ.get("CXX", "g++")
STD = os.environ.get("CXXSTD", "c++26")
RUNTIME_FLAGS = ["-O2", "-g", "-Wall", "-Wextra"]
# -fno-tree-pta: GCC 16's -O1 is super-linear on a long function full of temporaries with destructors.
# A 3143-line module body took over 25 minutes and 24 MB; without the analysis, 15 seconds and 1.2 MB,
# with no measurable cost at run time (fib and an object, dict and exception workload, within noise).
PROGRAM_FLAGS = ["-O1", "-w", "-fno-tree-pta"]
LIBRARY_FLAGS = ["-O0", "-w"]      # the standard library's units: a fifth of the compile time; speed is not a goal yet


def to_cpp(source: str, filename: str, namespace: str, prelude: bool = False) -> str:
    module: G.Module = lifetimes(to_l2(lower(source, filename)))
    wf2.check(module, lifetimes=True)
    return emit_module(module, namespace, filename, prelude)


def lowered_unit(source: str, filename: str, namespace: str) -> str:
    """to_cpp, kept under build/compiled/lowered by what decides its text: a closure's modules are
    the same for every program that imports them, and lowering them takes seconds each time. The
    compiler's macros are part of it: they decide which names the emitter escapes."""
    key = _key(source.encode(), filename.encode(), namespace.encode(), *_pipeline_bytes(), " ".join(sorted(header_macros())).encode())
    kept = BUILD / "lowered" / f"{namespace.replace('::', '_')}-{key}.cpp"
    if kept.exists():
        return kept.read_text(encoding="utf-8")
    text = to_cpp(source, filename, namespace)
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
               " ".join([cxx, std, *RUNTIME_FLAGS]).encode())
    out = BUILD / f"runtime-{key}"
    lib = out / "libbella.a"
    with _Lock(BUILD / "runtime.lock"):
        if lib.exists():
            return lib
        out.mkdir(parents=True, exist_ok=True)
        units = list(SOURCES)
        for p in [*(p for p, _ in PRELUDE), *NATIVE_IN_PYTHON]:
            cpp = out / f"prelude_{p.stem}.cpp"
            cpp.write_text(to_cpp(p.read_text(encoding="utf-8"), f"<bella prelude {p.name}>", f"bella::prelude_{p.stem}", prelude=True),
                           encoding="utf-8")
            units.append(cpp)
        objs = [out / f"{u.stem}.o" for u in units]
        with ThreadPoolExecutor(max(1, int(os.environ.get("BELLA_JOBS") or os.cpu_count() or 1))) as pool:
            list(pool.map(lambda uo: _compile(uo[0], uo[1], RUNTIME_FLAGS, cxx, std), zip(units, objs, strict=True)))
        subprocess.run(["ar", "rcs", str(lib) + ".tmp", *map(str, objs)], check=True)
        os.replace(str(lib) + ".tmp", lib)
    return lib


def main_unit(main_file: Path, modules: list[ProgramModule]) -> str:
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
            '#include "bella/runtime.hpp"\n\n' + decls + "\n" + preludes + "\n\n" + table +
            "\nint main(int argc, char** argv) {\n"
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
    units.append((main_unit(program, modules), f"{program.stem}-main", PROGRAM_FLAGS))
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
