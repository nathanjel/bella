"""The toy end-to-end slice: CPython == eval1(L1) == compiled C++ on named programs.

    python3 -m pipeline.slice --cxx g++ --std c++26 pipeline/examples/*.py

For each program: run it under the host CPython; lower it to L1, check wf1 and interpret it
with eval1; emit C++ with the toy backend, compile it against runtime/include and run it.
All three outputs must agree. A program whose header says ``# xfail: <reason>`` is expected
to fail on the C++ leg (a known gap such as BigInt); it is reported XFAIL, and XPASS if the
gap has closed. Generated C++ is written next to the program under examples/out/ and is
meant to be committed and read (readable output is a design goal).
"""
from __future__ import annotations

import argparse
import contextlib
import io
import os
import re
import subprocess
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

from pipeline.backend.emit_cpp import emit
from pipeline.l1.eval1 import Interpreter
from pipeline.l1.frontend import lower
from pipeline.l1.grammar import Unsupported
from pipeline.l1.wf import check

ROOT = Path(__file__).resolve().parents[1]
INCLUDE = ROOT / "runtime" / "include"


def run_cpython(path: Path) -> str:
    proc = subprocess.run([sys.executable, str(path)], capture_output=True, text=True, check=False, timeout=120)
    return proc.stdout + ("" if proc.returncode == 0 else f"<exit {proc.returncode}>\n{proc.stderr}")


def run_eval1(path: Path) -> str:
    module = lower(path.read_text(encoding="utf-8"), path.name)
    check(module)
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        Interpreter().run_module(module)
    return buf.getvalue()


def run_cpp(path: Path, out_dir: Path, cxx: str, std: str) -> str:
    module = lower(path.read_text(encoding="utf-8"), path.name)
    check(module)
    cpp = emit(module)
    out_dir.mkdir(parents=True, exist_ok=True)
    src = out_dir / f"{path.stem}.cpp"
    src.write_text(cpp, encoding="utf-8")
    exe = out_dir / f"{path.stem}.bin"
    build = subprocess.run([cxx, f"-std={std}", "-O1", "-Wall", "-I", str(INCLUDE), str(src), "-o", str(exe)],
                           capture_output=True, text=True, check=False)
    if build.returncode != 0:
        raise RuntimeError(f"C++ build failed:\n{build.stderr}")
    proc = subprocess.run([str(exe)], capture_output=True, text=True, check=False, timeout=120)
    return proc.stdout + ("" if proc.returncode == 0 else f"<exit {proc.returncode}>\n{proc.stderr}")


def xfail_reason(path: Path) -> str | None:
    for line in path.read_text(encoding="utf-8").splitlines()[:6]:
        m = re.match(r"^#\s*xfail:\s*(.+)$", line)
        if m:
            return m.group(1)
    return None


def one(prog: Path, out: Path, cxx: str, std: str) -> tuple[bool, str]:
    """(counts as a failure, report) for one program: CPython, eval1 and the compiled C++."""
    ref = run_cpython(prog)
    try:
        e1 = run_eval1(prog)
        e1_ok = e1 == ref
    except Unsupported as exc:
        e1, e1_ok = f"<unsupported: {exc}>", False
    xfail = xfail_reason(prog)
    try:
        cpp = run_cpp(prog, out, cxx, std)
        cpp_ok = cpp == ref
        cpp_note = "" if cpp_ok else cpp.strip().splitlines()[-1] if cpp.strip() else "<empty>"
    except (Unsupported, RuntimeError) as exc:
        cpp_ok, cpp_note = False, str(exc).strip().splitlines()[0]
    if xfail:
        status = "XFAIL" if not cpp_ok else "XPASS"
        failed = cpp_ok             # the gap closed: remove the xfail header
    else:
        status = "PASS" if (e1_ok and cpp_ok) else "FAIL"
        failed = not (e1_ok and cpp_ok)
    report = (f"{status:5} {prog.name:24} eval1={'ok' if e1_ok else 'DIFF'}  c++={'ok' if cpp_ok else 'DIFF'}"
              + (f"  [{xfail}]" if xfail else "") + ("" if cpp_ok else f"  :: {cpp_note}"))
    if not e1_ok:
        report += f"\n      eval1 output:\n{e1}"
    return failed, report


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("programs", nargs="+", type=Path)
    ap.add_argument("--cxx", default="g++")
    ap.add_argument("--std", default="c++26")
    ap.add_argument("--out", type=Path, default=ROOT / "pipeline" / "examples" / "out")
    args = ap.parse_args(argv)

    failures = 0
    # each program in a process of its own (BELLA_JOBS, else one per CPU), reported in order
    jobs = max(1, int(os.environ.get("BELLA_JOBS") or os.cpu_count() or 1))
    with ProcessPoolExecutor(jobs) as pool:
        futures = [pool.submit(one, prog, args.out, args.cxx, args.std) for prog in args.programs]
        for future in futures:
            failed, report = future.result()
            failures += failed
            print(report)
    print(f"\nslice: {len(args.programs) - failures}/{len(args.programs)} as expected ({args.cxx} -std={args.std}); "
          f"generated C++ in {args.out}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
