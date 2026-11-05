#!/usr/bin/env python3
"""runtime/include/bella/object.hpp against CPython and the reference model, in lockstep.

    python3 runtime/tests/object_differential.py --cxx g++ --std c++26 --iterations 3000 [--seed N]

TODO task 3's done-when: "the C++ object model passes the same stateful test through a thin
Python binding". The oracle's random programs (refmodel/oracle.py) run three ways at once: on the
reference model, on CPython's classes, and on the header through runtime/tests/object_binding.cpp
(built here, loaded with ctypes). After every operation the header's outcome and the deaths it
logged must equal CPython's, and after every operation every attribute of every object is read
through the header's inline caches and compared with CPython. The header runs in its checking
mode: a cached read is compared with the generic lookup, and an object dying while an entry a live
class still validates names it, or a cached read of a dead borrowed `found`, stops the run.
"""
from __future__ import annotations

import argparse
import ast
import ctypes
import os
import random
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from refmodel.oracle import Mismatch, World  # noqa: E402


def compile_binding(cxx: str, std: str, out: Path, sanitize: bool = False) -> None:
    src = ROOT / "runtime" / "tests" / "object_binding.cpp"
    flags = ["-fsanitize=address,undefined", "-fno-omit-frame-pointer"] if sanitize else []
    subprocess.run([cxx, f"-std={std}", "-O1", "-g", "-shared", "-fPIC", "-Wall", "-Wextra", *flags,
                    f"-I{ROOT / 'runtime' / 'include'}", str(src), "-o", str(out)], check=True)


def build(cxx: str, std: str, out: Path, sanitize: bool = False) -> ctypes.CDLL:
    compile_binding(cxx, std, out, sanitize)
    lib = ctypes.CDLL(str(out))
    lib.bw_new.argtypes = [ctypes.c_int]
    lib.bw_new.restype = ctypes.c_void_p
    lib.bw_free.argtypes = [ctypes.c_void_p]
    for fn in (lib.bw_apply, lib.bw_sweep, lib.bw_deaths):
        fn.restype = ctypes.c_char_p
    lib.bw_apply.argtypes = [ctypes.c_void_p, ctypes.c_char_p]
    lib.bw_sweep.argtypes = [ctypes.c_void_p]
    lib.bw_deaths.argtypes = [ctypes.c_void_p]
    lib.bw_hits.argtypes = [ctypes.c_void_p]
    lib.bw_hits.restype = ctypes.c_ulonglong
    return lib


def encode(op: tuple[Any, ...]) -> str:
    def value(v: Any) -> str:
        if isinstance(v, tuple):
            return f"t:{v[1][1:]}"            # ("T", "t5")
        return f"i:{v}"
    kind, *args = op
    if kind == "get":
        return f"get {args[0]} {args[1]} {int(args[2])}"
    if kind in ("set", "set_class_attr"):
        return f"{kind} {args[0]} {args[1]} {value(args[2])}"
    if kind == "revive":
        return f"revive {args[0]} {args[1]} {value(args[2])}"
    if kind == "replace_dict":
        return f"replace_dict {args[0]} {-1 if args[1] is None else args[1]}"
    if kind == "install_descriptor":
        return f"install_descriptor {args[0]} {args[1]} {int(args[2])}"
    return " ".join(str(x) for x in (kind, *args))


def answer(raw: bytes) -> Any:
    text = raw.decode()
    if text.startswith("MODEL ERROR"):
        raise Mismatch(f"object.hpp: {text}")
    return ast.literal_eval(text)


def run(lib: ctypes.CDLL, iterations: int, seed: int, ops_per_world: int = 60) -> tuple[int, int, int, int]:
    """Returns (worlds, operations, deaths compared, cache hits in the header)."""
    rng = random.Random(seed)
    worlds = ops = deaths = hits = 0
    while ops < iterations:
        world = World()
        cpp = lib.bw_new(1)
        worlds += 1
        try:
            for _ in range(ops_per_world):
                op = world.random_op(rng)
                world.apply(op)                           # the model against CPython
                assert world.last is not None
                real = world.last[1]
                got = answer(lib.bw_apply(cpp, encode(op).encode()))
                if got != real:
                    raise Mismatch(f"{op}: object.hpp {got!r} != cpython {real!r}\nlog:\n" + "\n".join(map(repr, world.log)))
                died = answer(lib.bw_deaths(cpp))
                if died != world.last_deaths:
                    raise Mismatch(f"{op}: deaths in object.hpp {died} != in cpython {world.last_deaths}\nlog:\n"
                                   + "\n".join(map(repr, world.log)))
                deaths += len(died)
                world.sweep()
                swept = answer(lib.bw_sweep(cpp))
                real_sweep = world.real_sweep()
                if swept != real_sweep:
                    bad = next(i for i, (a, b) in enumerate(zip(swept, real_sweep, strict=True)) if a != b)
                    raise Mismatch(f"after {op}: object.hpp read {swept[bad]!r}, cpython {real_sweep[bad]!r} "
                                   f"(object {bad // 10}, name {bad % 10})\nlog:\n" + "\n".join(map(repr, world.log)))
                ops += 1
            hits += lib.bw_hits(cpp)
        finally:
            lib.bw_free(cpp)
    return worlds, ops, deaths, hits


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cxx", default="g++")
    ap.add_argument("--std", default="c++26")
    ap.add_argument("--iterations", type=int, default=3000)
    ap.add_argument("--seed", type=int, default=20261102)
    ap.add_argument("--sanitize", action="store_true", help="the header under AddressSanitizer and UBSan")
    args = ap.parse_args()
    with tempfile.TemporaryDirectory() as tmp:
        if args.sanitize and not os.environ.get("BELLA_ASAN_CHILD"):
            # ASan must be loaded before the interpreter: build, find the runtime the library links
            # (on some distributions libasan.so is a linker script), and run again with it preloaded
            out = Path(tmp) / "libbella_object_binding.so"
            compile_binding(args.cxx, args.std, out, sanitize=True)
            ldd = subprocess.run(["ldd", str(out)], capture_output=True, text=True, check=True).stdout
            def linked(name: str) -> str:
                return next(line.split("=>")[1].split()[0] for line in ldd.splitlines() if name in line)
            # libstdc++ too: the interpreter does not load it, and ASan's __cxa_throw interceptor
            # needs the real one when it starts (some GCC releases fail a CHECK without it)
            preload = f"{linked('libasan')} {linked('libstdc++')}"
            env = dict(os.environ, LD_PRELOAD=preload, ASAN_OPTIONS="detect_leaks=0:verify_asan_link_order=0", BELLA_ASAN_CHILD="1")
            return subprocess.run([sys.executable, *sys.argv], env=env, check=False).returncode
        lib = build(args.cxx, args.std, Path(tmp) / "libbella_object_binding.so", args.sanitize)
        try:
            worlds, ops, deaths, hits = run(lib, args.iterations, args.seed)
        except Mismatch as exc:
            print(f"MISMATCH (seed {args.seed}):\n{exc}", file=sys.stderr)
            return 1
    print(f"object.hpp: {ops} operations over {worlds} worlds, seed {args.seed}: header == model == CPython; "
          f"{deaths} deaths in CPython's order; {hits} inline cache hits")
    return 0


if __name__ == "__main__":
    sys.exit(main())
