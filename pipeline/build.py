#!/usr/bin/env python3
"""bella build: a program through L2 into C++26, compiled and linked against the runtime.

    python3 pipeline/build.py PROGRAM.py [-o BINARY]           build; print the binary's path
    python3 pipeline/build.py --run PROGRAM.py [ARGS...]        build, then run it as the program

The program is lowered (frontend, to-anf, lifetimes, wf2) and emitted by pipeline/backend/cpp.py;
the runtime library is runtime/src/*.cpp and the prelude (runtime/prelude/builtins.py, compiled
the same way), built once per content hash under build/compiled/ and shared by every program.
A construct the pipeline refuses stops the build with exit 70, as the evaluators refuse.
"""
from __future__ import annotations

import fcntl
import hashlib
import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from pipeline.backend.cpp import emit_module  # noqa: E402
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
PRELUDE = [ROOT / "runtime" / "prelude" / "build_class.py", ROOT / "runtime" / "prelude" / "builtins.py"]   # in this order
CXX = os.environ.get("CXX", "g++")
STD = os.environ.get("CXXSTD", "c++26")
RUNTIME_FLAGS = ["-O2", "-g", "-Wall", "-Wextra"]
PROGRAM_FLAGS = ["-O1", "-w"]


def to_cpp(source: str, filename: str, namespace: str, prelude: bool = False) -> str:
    module: G.Module = lifetimes(to_l2(lower(source, filename)))
    wf2.check(module, lifetimes=True)
    return emit_module(module, namespace, filename, prelude)


def _key(*parts: bytes) -> str:
    h = hashlib.sha256()
    for p in parts:
        h.update(hashlib.sha256(p).digest())
    return h.hexdigest()[:16]


def _pipeline_bytes() -> list[bytes]:
    """Everything that decides what a program compiles to: the compiler's own sources."""
    files = sorted((ROOT / "pipeline").rglob("*.py")) + sorted(INCLUDE.rglob("*.hpp"))
    return [f.read_bytes() for f in files if "tests" not in f.parts]


def _compile(src: Path, obj: Path, flags: list[str], cxx: str, std: str) -> None:
    proc = subprocess.run([cxx, f"-std={std}", *flags, f"-I{INCLUDE}", "-c", str(src), "-o", str(obj)],
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
    key = _key(*(s.read_bytes() for s in [*SOURCES, *INCLUDED]), *(p.read_bytes() for p in PRELUDE), *_pipeline_bytes(),
               " ".join([cxx, std, *RUNTIME_FLAGS]).encode())
    out = BUILD / f"runtime-{key}"
    lib = out / "libbella.a"
    with _Lock(BUILD / "runtime.lock"):
        if lib.exists():
            return lib
        out.mkdir(parents=True, exist_ok=True)
        units = list(SOURCES)
        for p in PRELUDE:
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


def main_unit(program_cpp: str) -> str:
    preludes = "\n".join(f"namespace bella::prelude_{p.stem} {{ ::bella::Ref module_body(::bella::Module* m); }}" for p in PRELUDE)
    bodies = ", ".join(f"::bella::prelude_{p.stem}::module_body" for p in PRELUDE)
    return (program_cpp + "\n" + preludes + "\n\nint main(int argc, char** argv) {\n"
            f"    return ::bella::run_main(argc, argv, ::bella::m_main::module_body, {{{bodies}}});\n}}\n")


def build(program: Path, filename: str, cxx: str = CXX, std: str = STD, keep: Path | None = None) -> Path:
    """The program's binary; `keep`: also write its C++ there (the committed examples)."""
    lib = runtime_library(cxx, std)
    cpp = main_unit(to_cpp(program.read_text(encoding="utf-8"), filename, "bella::m_main"))
    if keep is not None:
        keep.parent.mkdir(parents=True, exist_ok=True)
        keep.write_text(cpp, encoding="utf-8")
    key = _key(cpp.encode(), lib.parent.name.encode(), " ".join([cxx, std, *PROGRAM_FLAGS]).encode())
    out = BUILD / f"{program.stem}-{key}"
    exe = out / program.stem
    if exe.exists():
        return exe
    out.mkdir(parents=True, exist_ok=True)
    src = out / f"{program.stem}.cpp"
    src.write_text(cpp, encoding="utf-8")
    proc = subprocess.run([cxx, f"-std={std}", *PROGRAM_FLAGS, f"-I{INCLUDE}", str(src), str(lib), "-o", str(exe) + ".tmp"],
                          capture_output=True, text=True, check=False)
    if proc.returncode != 0:
        raise RuntimeError(f"{cxx} failed on {src}:\n{proc.stderr[-4000:]}")
    os.replace(str(exe) + ".tmp", exe)
    return exe


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
        exe = build(program, argv[0])
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
