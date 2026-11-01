#!/usr/bin/env python3
"""Compile, link and run every C++ feature probe; write a Markdown report.

    python3 tools/probe_toolchain.py --cxx g++ --std c++26 --out toolchain-probes.md

Each probe under runtime/probes names what it needs; the report says, for the compiler that
was actually used, which of the C++23/26 facilities the design relies on are available today
(design document, sections 9 and 10.3). The report is informational: a missing facility is
a known stand-in (xenium, libuv, the reference simd), not a failure.
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROBES = ROOT / "runtime" / "probes"


def header(path: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines()[:5]:
        m = re.match(r"^//\s*(probe|needs|flags):\s*(.+?)\s*$", line)
        if m:
            out[m.group(1)] = m.group(2)
    return out


def run_probe(path: Path, cxx: str, std: str) -> tuple[str, str]:
    h = header(path)
    flags = h.get("flags", "").split()
    with tempfile.TemporaryDirectory() as tmp:
        exe = Path(tmp) / "probe"
        cmd = [cxx, f"-std={std}", "-O0", str(path), "-o", str(exe), *flags]
        build = subprocess.run(cmd, capture_output=True, text=True, check=False, timeout=600)
        if build.returncode != 0:
            first = next((ln for ln in build.stderr.splitlines() if "error" in ln or "fatal" in ln), build.stderr.strip()[:200])
            return "compile-fail", first.replace(str(ROOT) + "/", "").strip()[:160]
        run = subprocess.run([str(exe)], capture_output=True, text=True, check=False, timeout=60)
        if run.returncode != 0:
            return "run-fail", (run.stderr.strip() or f"exit {run.returncode}")[:160]
        return "ok", run.stdout.strip()[:160]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--cxx", default="g++")
    ap.add_argument("--std", default="c++26")
    ap.add_argument("--out", type=Path, default=ROOT / "toolchain-probes.md")
    args = ap.parse_args(argv)

    version = subprocess.run([args.cxx, "--version"], capture_output=True, text=True, check=False).stdout.splitlines()[0]
    rows = []
    for probe in sorted(PROBES.glob("*.cpp")):
        h = header(probe)
        status, detail = run_probe(probe, args.cxx, args.std)
        rows.append((h.get("probe", probe.stem), status, h.get("needs", ""), h.get("flags", ""), detail))
        print(f"{status:13} {h.get('probe', probe.stem):24} {detail[:80]}")

    ok = sum(1 for r in rows if r[1] == "ok")
    lines = [
        "# Toolchain probes",
        "",
        f"Compiler: `{version}` with `-std={args.std}`. {ok}/{len(rows)} probes pass.",
        "",
        "A failing probe means the facility is not available on this toolchain yet; the design names",
        "a stand-in for each (design document, section 10.3). Regenerate with `make probes`.",
        "",
        "| Probe | Status | Needs | Flags | Detail |",
        "| --- | --- | --- | --- | --- |",
    ]
    for name, status, needs, flags, detail in rows:
        lines.append(f"| {name} | {status} | {needs} | `{flags}` | {detail.replace('|', '\\|')} |")
    args.out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"\n{ok}/{len(rows)} probes pass on {version}; report: {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
