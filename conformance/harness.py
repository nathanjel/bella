#!/usr/bin/env python3
"""Conformance harness (dialect specification v0.3, section 10).

    harness.py record  [--python PATH] [--allow-unpinned] [--filter SUBSTR]
    harness.py check   --runner "CMD {case}" [--allow-unpinned] [--filter SUBSTR]
    harness.py list

`record` runs every case under the reference CPython and stores the observable trace in
conformance/expected/<case>.json. `check` runs every case through RUNNER (a command with
`{case}` standing for the case path -- for now `python3 {case}`, later the compiled binary)
and compares against the recorded trace.

What is compared (spec, section 2, first table): stdout byte for byte; stderr after the
D-06 and D-08 masks (traceback frames reduced to file and line, the runtime-generated wording
of built-in exception messages masked per exception type); the exit status. Cases print
structured exception payloads themselves (class name, args, attributes), never str(exc)
of a built-in exception, so the masks never hide anything the dialect keeps observable.

Cases carry a header:
    # clause: C-9-01
    # spec: section 9
    # status: P1 | P2+ | X
    # source: review round 3, finding 1
A status X case is one the compiler must reject; `check` expects the runner to fail and to
name the exclusion id given in `# expect: E-01`.
"""
from __future__ import annotations

import argparse
import builtins
import json
import os
import re
import subprocess
import sys
import tomllib
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CASES = ROOT / "cases"
EXPECTED = ROOT / "expected"
PROJECT = ROOT.parent

_FRAME = re.compile(r'^(\s*)File "(.+?)", line (\d+)(, in .+)?$')
_EXC_LINE = re.compile(r"^([A-Za-z_][\w.]*): (.*)$")
_BUILTIN_EXC = {
    n for n in dir(builtins)
    if isinstance(getattr(builtins, n), type) and issubclass(getattr(builtins, n), BaseException)
}


@dataclass
class Header:
    clause: str
    spec: str
    status: str
    source: str
    expect: str | None


def read_header(path: Path) -> Header:
    fields: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines()[:12]:
        m = re.match(r"^#\s*(clause|spec|status|source|expect):\s*(.+?)\s*$", line)
        if m:
            fields[m.group(1)] = m.group(2)
    return Header(fields.get("clause", path.stem), fields.get("spec", "?"), fields.get("status", "P1"),
                  fields.get("source", ""), fields.get("expect"))


def mask_stderr(text: str) -> str:
    """D-06: traceback frames keep file (basename) and line; source echo lines are dropped.
    D-08: the message of a built-in exception on a 'Type: message' line is masked."""
    out: list[str] = []
    skip_echo = False
    for line in text.splitlines():
        m = _FRAME.match(line)
        if m:
            out.append(f'{m.group(1)}File "{Path(m.group(2)).name}", line {m.group(3)}{m.group(4) or ""}')
            skip_echo = True
            continue
        if skip_echo and (line.startswith("    ") or line.strip() == "" or set(line.strip()) <= set("~^")):
            continue
        skip_echo = False
        e = _EXC_LINE.match(line)
        if e and e.group(1).rpartition(".")[2] in _BUILTIN_EXC:
            out.append(f"{e.group(1)}: <wording masked by D-08>")
            continue
        out.append(line)
    return "\n".join(out) + ("\n" if text.endswith("\n") else "")


def run_case(cmd: list[str], case: Path) -> dict[str, object]:
    env = dict(os.environ, PYTHONHASHSEED="0", PYTHONUTF8="1", PYTHONIOENCODING="utf-8")
    proc = subprocess.run(cmd, cwd=CASES, capture_output=True, text=True, env=env, timeout=120, check=False)
    return {"stdout": proc.stdout, "stderr": mask_stderr(proc.stderr), "exit_code": proc.returncode}


def iter_cases(filter_: str | None) -> list[Path]:
    cases = sorted(p for p in CASES.glob("*.py") if p.name[0] in "CX")
    return [c for c in cases if not filter_ or filter_ in c.name]


def pinned_python() -> str:
    data = tomllib.loads((PROJECT / "bella.toml").read_text(encoding="utf-8"))
    return str(data["reference"]["python"])


def python_version(python: str) -> str:
    out = subprocess.run([python, "-c", "import sys; print('.'.join(map(str, sys.version_info[:3])))"],
                         capture_output=True, text=True, check=True)
    return out.stdout.strip()


# ------------------------------------------------------------------------------------------

def cmd_record(args: argparse.Namespace) -> int:
    version = python_version(args.python)
    pinned = pinned_python()
    if version != pinned and not args.allow_unpinned:
        print(f"record: {args.python} is {version}; expectations must be recorded with {pinned} "
              f"(--allow-unpinned records a non-authoritative set)", file=sys.stderr)
        return 2
    EXPECTED.mkdir(exist_ok=True)
    n = 0
    for case in iter_cases(args.filter):
        header = read_header(case)
        if header.status == "X":
            continue  # excluded constructs are rejected at compile time; nothing to record
        trace = run_case([args.python, case.name], case)
        record = {"case": case.name, "clause": header.clause, "spec": header.spec, "status": header.status,
                  "source": header.source, "recorded_with": version, "authoritative": version == pinned, **trace}
        (EXPECTED / f"{case.stem}.json").write_text(json.dumps(record, indent=1) + "\n", encoding="utf-8")
        n += 1
        print(f"recorded {case.name:48} exit={trace['exit_code']}")
    print(f"{n} cases recorded with CPython {version}{'' if version == pinned else '  [UNPINNED]'}")
    return 0


def cmd_check(args: argparse.Namespace) -> int:
    failures = 0
    total = 0
    for case in iter_cases(args.filter):
        header = read_header(case)
        cmd = [part.replace("{case}", case.name) for part in args.runner.split()]
        if header.status == "X":
            trace = run_case(cmd, case)
            ok = trace["exit_code"] != 0 and (header.expect or "") in str(trace["stderr"])
            print(f"{'PASS' if ok else 'FAIL'}  {case.name:48} (must be rejected with {header.expect})")
            failures += not ok
            total += 1
            continue
        expected_path = EXPECTED / f"{case.stem}.json"
        if not expected_path.exists():
            print(f"SKIP  {case.name:48} no expectation recorded")
            continue
        expected = json.loads(expected_path.read_text(encoding="utf-8"))
        if not expected.get("authoritative") and not args.allow_unpinned:
            print(f"SKIP  {case.name:48} expectation recorded with {expected['recorded_with']} (unpinned)")
            continue
        actual = run_case(cmd, case)
        total += 1
        diffs = [k for k in ("stdout", "stderr", "exit_code") if actual[k] != expected[k]]
        if diffs:
            failures += 1
            print(f"FAIL  {case.name:48} differs in {', '.join(diffs)}")
            for k in diffs:
                print(f"      expected {k}: {expected[k]!r}")
                print(f"      actual   {k}: {actual[k]!r}")
        else:
            print(f"PASS  {case.name}")
    print(f"\n{total - failures}/{total} passed")
    return 1 if failures else 0


def cmd_list(args: argparse.Namespace) -> int:
    for case in iter_cases(args.filter):
        h = read_header(case)
        print(f"{h.clause:8} {h.status:4} {h.spec:12} {case.name:48} {h.source}")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("record")
    r.add_argument("--python", default=sys.executable)
    r.add_argument("--allow-unpinned", action="store_true")
    r.add_argument("--filter")
    r.set_defaults(fn=cmd_record)
    c = sub.add_parser("check")
    c.add_argument("--runner", required=True, help='command with {case}, e.g. "python3 {case}"')
    c.add_argument("--allow-unpinned", action="store_true")
    c.add_argument("--filter")
    c.set_defaults(fn=cmd_check)
    ls = sub.add_parser("list")
    ls.add_argument("--filter")
    ls.set_defaults(fn=cmd_list)
    args = ap.parse_args(argv)
    return int(args.fn(args))


if __name__ == "__main__":
    raise SystemExit(main())
