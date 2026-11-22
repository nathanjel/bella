"""The argument counts of the methods of the built-in types: each called unbound with too few and too many arguments.

`argument_counts_sweep.txt` makes an object of each of 168 types (the built-in ones, every exception class, the types the
preludes write for collections, functools, itertools, operator, io, struct, zlib, re, contextvars, weakref, _thread, csv,
ast and typing) and calls every method CPython's type has (a wrapper, a method or a class method descriptor, a built-in
function: 4,933 names) as `T.name()`, `T.name(x)`, `T.name(x, 0)`, with two and three extra arguments, and with a keyword,
printing the class of what is raised or the type of what comes back. One process a type on both sides; where the compiled
one stops by name at a method, it goes on in a new process at the next (`argument_counts_stops.txt` lists the 183 stops:
163 are `__sizeof__`, which the runtime does not answer yet).

Review A33's saved outputs showed `object.__lt__(x)` returning NotImplemented without an operand (RL-752), and review A34's
sweep of the same class ended at each type's first stop. This one found, beyond RL-752: `range.__init__(r, 1)` and the same
on 22 more types whose allocator is their own or absent raised TypeError where CPython's `object.__init__` lets it pass
(`allocator_is_objects`, `runtime/src/types.cpp`); `KeyError.__str__(e, 1)` and `ImportError.__str__(e, 1)` gave a str;
`object.__getstate__` of a class and of a module gave None for their dict; and `int.to_bytes`, `int.from_bytes`,
`str.split`, `str.rsplit` and `str.replace` stopped by name at an unexpected keyword, which is a TypeError.

Run under pytest or directly: python3 -m pipeline.tests.test_argument_counts
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from pipeline.build import build

HERE = Path(__file__).resolve().parent
CASES = ("none", "self", "one", "two", "three", "keyword")


def _run(command: list[str], folder: Path) -> subprocess.CompletedProcess[str]:
    env = {**os.environ, "PYTHONHASHSEED": "0", "PYTHONWARNINGS": "ignore"}
    return subprocess.run(command, capture_output=True, text=True, env=env, cwd=folder, timeout=300, stdin=subprocess.DEVNULL)


def _one(key: str, program: Path, binary: str, folder: Path) -> tuple[list[str], list[str]]:
    """The rows of one type that differ, and the names at which the compiled side stopped."""
    names = _run([sys.executable, str(program), key, "names"], folder).stdout.strip()
    count = len(names.split(","))
    reference = _run([sys.executable, str(program), key, "0", names], folder)
    assert reference.returncode == 0, (key, reference.stderr[-300:])
    want = {int(line.split()[0]): line.split() for line in reference.stdout.splitlines()}
    assert len(want) == count, (key, len(want), count)
    got: dict[int, list[str]] = {}
    stops: list[str] = []
    start = 0
    while start < count:
        compiled = _run([binary, key, str(start), names], folder)
        rows = [line.split() for line in compiled.stdout.splitlines()]
        for row in rows:
            got[int(row[0])] = row
        if compiled.returncode == 0:
            break
        assert compiled.returncode == 70 and "bella: not implemented: " in compiled.stderr, (key, compiled.returncode, compiled.stderr[-300:])
        at = max((int(row[0]) for row in rows), default=start - 1) + 1   # the name this run stopped at: the one after its last row
        stops.append(f"{key} {names.split(',')[at]}")
        start = at + 1
    wrong = [f"{key}.{want[i][1]}: " + "; ".join(f"{case}: CPython {a}, compiled {b}" for case, a, b in zip(CASES, want[i][2:], got[i][2:], strict=True) if a != b)
             for i in sorted(want) if i in got and got[i] != want[i]]
    missing = [f"{key}.{want[i][1]}: no row" for i in sorted(want) if i not in got and f"{key} {want[i][1]}" not in stops]
    return wrong + missing, stops


def test_the_methods_of_the_built_in_types_count_their_arguments() -> None:
    if shutil.which("g++") is None:
        return
    folder = Path(tempfile.mkdtemp(prefix="bella-arguments-"))
    try:
        program = folder / "prog.py"
        program.write_text((HERE / "argument_counts_sweep.txt").read_text(encoding="utf-8"), encoding="utf-8")
        binary = str(build(program, "prog.py", notes=False))
        keys = _run([sys.executable, str(program), "object", "keys"], folder).stdout.strip().split(",")
        assert len(keys) >= 168, len(keys)
        with ThreadPoolExecutor(max_workers=8) as pool:
            results = list(pool.map(lambda key: _one(key, program, binary, folder), keys))
        wrong = [row for rows, _ in results for row in rows]
        assert not wrong, "\n".join(wrong[:60])
        stops = sorted(stop for _, stopped in results for stop in stopped)
        listed = (HERE / "argument_counts_stops.txt").read_text(encoding="utf-8").split("\n")[:-1]
        assert stops == listed, sorted(set(stops) ^ set(listed))
    finally:
        shutil.rmtree(folder, ignore_errors=True)


if __name__ == "__main__":
    test_the_methods_of_the_built_in_types_count_their_arguments()
    print("ok")
