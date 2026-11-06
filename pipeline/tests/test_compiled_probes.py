"""The release-point probes (pipeline/tests/test_l2_probes.py) compiled: every kind of place CPython
drops a reference, at module level and in a function, through L2 and the C++ emitter, against
CPython. A probe the compiled runtime cannot run yet must stop with a refusal (exit 70), never with
other output (docs/emitter.md; generators come with step 3b).

Run under pytest or directly: python3 -m pipeline.tests.test_compiled_probes
"""
from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

from pipeline.build import build
from pipeline.tests.test_l2_probes import PRELUDE, TEMPLATES, program

CASES = [(kind, in_function) for kind in TEMPLATES for in_function in (False, True)]


def pytest_generate_tests(metafunc: Any) -> None:
    if {"kind", "in_function"} <= set(metafunc.fixturenames):
        metafunc.parametrize(("kind", "in_function"), CASES,
                             ids=[f"{k}-{'function' if f else 'module'}" for k, f in CASES])


def test_compiled_release_point(kind: str, in_function: bool) -> None:
    if shutil.which("g++") is None:
        return
    with tempfile.TemporaryDirectory() as tmp:
        prog = Path(tmp, "probe.py")
        prog.write_text(PRELUDE + program(TEMPLATES[kind], in_function), encoding="utf-8")
        ref = subprocess.run([sys.executable, str(prog)], capture_output=True, text=True, check=False)
        got = subprocess.run([str(build(prog, "probe.py"))], capture_output=True, text=True, check=False)
    where = "in a function" if in_function else "at module level"
    assert (got.stdout, got.returncode) == (ref.stdout, ref.returncode), (
        f"{kind} ({where}):\n--- compiled\n{got.stdout}{got.stderr}--- cpython\n{ref.stdout}")


if __name__ == "__main__":
    for case in CASES:
        test_compiled_release_point(*case)
    print(f"ok test_compiled_release_point ({len(CASES)} probes)")
