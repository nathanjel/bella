#!/usr/bin/env python3
"""Conformance harness (dialect specification v0.7, section 10).

    harness.py record  [--python PATH] [--allow-unpinned] [--filter SUBSTR]
    harness.py verify  [--python PATH] [--filter SUBSTR]
    harness.py check   --runner "CMD {case}" [--allow-unpinned] [--filter SUBSTR]
    harness.py list

`record` runs every case under the reference CPython and stores the observable trace in
conformance/expected/<case>.json. `verify` re-runs the corpus under the pinned CPython and
requires it to reproduce the recorded traces (the oracle checked, not Bella: stale or
non-deterministic expectations fail). `check` runs every case through RUNNER (a command with
`{case}` standing for the case path -- the compiled binary once it exists) and compares
against the recorded trace. Both fail closed (review 2026-11-01, astra-low-01 #7): a selected
case without an authoritative expectation is a failure, not a skip, and a run that selects
no case is an error.

What is compared (spec, section 2, first table): stdout byte for byte; stderr after the
D-06 and D-08 masks (traceback frames reduced to file and line; the runtime-generated wording
of a built-in exception's message masked only for the exception types the case declares in
`# mask:`, so a user-supplied message stays observable unless a case says otherwise); the
exit status. Cases print structured exception payloads themselves (class name, args,
attributes), never str(exc) of a built-in exception the runtime raised.

Cases carry a header:
    # clause: C-9-01
    # spec: section 9
    # status: P1 | P2+ | X
    # source: review round 3, finding 1
    # mask: TypeError, KeyError     (optional: D-08 masks the wording of these types only)
    # deviation: D-20               (optional: the case differs by this registered deviation)
A status X case is one the compiler must reject; `check` expects the runner to fail and to
name the exclusion id given in `# expect: E-01`.

A status P2+ case is recorded and verified on CPython like any other (it is the behaviour the
milestone must reach), but `check` requires the runner to refuse it until then: a non-zero
exit with the spec's marker `[P2+]` in stderr, and the `# expect:` text when the case gives
one (spec section 10: a [P2+] clause must fail with the milestone-naming error, never pass by
accident).

A case that declares `# deviation: D-nn` has two expectations: CPython's trace, and the trace
of CPython made to show the deviation (`expected/<case>.D-nn.json`), which is what `check`
requires of the runner. Only deviations that CPython can be made to show are accepted; today
that is D-20 (the phase-1 omissions and codec set), simulated by blocking those modules at
start-up (conformance/simulate/sitecustomize.py). `record` refuses a deviation case whose two
traces are equal, since the declaration would then claim a difference that does not exist.
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


P2_MARKER = "[P2+]"
STATUSES = ("P1", "P2+", "X")


@dataclass
class Header:
    clause: str
    spec: str
    status: str
    source: str
    expect: str | None
    mask: frozenset[str] = frozenset()
    deviation: str | None = None


def read_header(path: Path) -> Header:
    fields: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines()[:12]:
        m = re.match(r"^#\s*(clause|spec|status|source|expect|mask|deviation):\s*(.+?)\s*$", line)
        if m:
            fields[m.group(1)] = m.group(2)
    mask = frozenset(t.strip() for t in fields.get("mask", "").split(",") if t.strip())
    unknown = mask - _BUILTIN_EXC
    if unknown:
        raise ValueError(f"{path.name}: '# mask:' names non-built-in exception types {sorted(unknown)}")
    status = fields.get("status", "P1")
    if status not in STATUSES:
        raise ValueError(f"{path.name}: status {status!r} is not one of {', '.join(STATUSES)}")
    deviation = fields.get("deviation")
    if deviation is not None and deviation not in SIMULATIONS:
        raise ValueError(f"{path.name}: deviation {deviation} cannot be shown on CPython "
                         f"(the harness simulates {', '.join(sorted(SIMULATIONS))})")
    return Header(fields.get("clause", path.stem), fields.get("spec", "?"), status,
                  fields.get("source", ""), fields.get("expect"), mask, deviation)


# ---- deviations the reference CPython can be made to show ---------------------------------

def _phase1_blocked(python: str) -> list[str]:
    """D-20: the modules phase 1 does not have. The manifest's omissions, and every codec module
    outside the phase-1 set (the codec search reaches only those the manifest compiles)."""
    manifest = tomllib.loads((PROJECT / "manifest.toml").read_text(encoding="utf-8"))
    blocked = {t for targets in manifest.get("omissions", {}).values() for t in targets}
    compiled = set(manifest["phase1"]["compiled"])
    listing = subprocess.run(
        [python, "-I", "-c", "import encodings, json, os; print(json.dumps(os.listdir(encodings.__path__[0])))"],
        capture_output=True, text=True, check=True).stdout
    for entry in sorted(json.loads(listing)):
        name = entry.removesuffix(".py")
        if entry.endswith(".py") and name != "__init__" and f"encodings.{name}" not in compiled:
            blocked.add(f"encodings.{name}")
    return sorted(blocked)


SIMULATIONS = {"D-20": _phase1_blocked}


def simulation_env(deviation: str | None, python: str) -> dict[str, str]:
    if deviation is None:
        return {}
    return {"PYTHONPATH": str(ROOT / "simulate"),
            "BELLA_SIMULATE_BLOCK": ",".join(SIMULATIONS[deviation](python))}


def expectation_path(case: Path, deviation: str | None = None) -> Path:
    return EXPECTED / (f"{case.stem}.{deviation}.json" if deviation else f"{case.stem}.json")


def mask_stderr(text: str, masked: frozenset[str] = frozenset()) -> str:
    """D-06: traceback frames keep file (basename) and line; source echo lines are dropped.
    D-08: the message on a 'Type: message' line is masked only for the built-in exception types
    the case declares (`masked`); everything else, user-supplied messages included, is compared."""
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
        if e and e.group(1).rpartition(".")[2] in masked:
            out.append(f"{e.group(1)}: <wording masked by D-08>")
            continue
        out.append(line)
    return "\n".join(out) + ("\n" if text.endswith("\n") else "")


def run_case(cmd: list[str], case: Path, masked: frozenset[str] = frozenset(),
             extra_env: dict[str, str] | None = None) -> dict[str, object]:
    env = dict(os.environ, PYTHONHASHSEED="0", PYTHONUTF8="1", PYTHONIOENCODING="utf-8", **(extra_env or {}))
    proc = subprocess.run(cmd, cwd=CASES, capture_output=True, text=True, env=env, timeout=120, check=False)
    return {"stdout": proc.stdout, "stderr": mask_stderr(proc.stderr, masked), "exit_code": proc.returncode}


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
        traces = {None: run_case([args.python, case.name], case, header.mask)}
        if header.deviation:
            traces[header.deviation] = run_case([args.python, case.name], case, header.mask,
                                                simulation_env(header.deviation, args.python))
            if traces[header.deviation] == traces[None]:
                print(f"record: {case.name} declares {header.deviation}, but CPython shows no difference under "
                      f"its simulation", file=sys.stderr)
                return 1
        for deviation, trace in traces.items():
            record = {"case": case.name, "clause": header.clause, "spec": header.spec, "status": header.status,
                      "source": header.source, **({"deviation": deviation} if deviation else {}),
                      "recorded_with": version, "authoritative": version == pinned, **trace}
            expectation_path(case, deviation).write_text(json.dumps(record, indent=1) + "\n", encoding="utf-8")
        n += 1
        print(f"recorded {case.name:48} exit={traces[None]['exit_code']}"
              f"{f'  (+ {header.deviation} trace)' if header.deviation else ''}")
    print(f"{n} cases recorded with CPython {version}{'' if version == pinned else '  [UNPINNED]'}")
    return 0


def _compare(cmd: list[str], case: Path, header: Header, allow_unpinned: bool, deviation: str | None = None,
             extra_env: dict[str, str] | None = None) -> tuple[str, list[str]]:
    """('PASS' | 'FAIL', report lines) for one case against its recorded expectation (CPython's,
    or the one under `deviation`)."""
    label = f"{case.name} [{deviation}]" if deviation else case.name
    expected_path = expectation_path(case, deviation)
    if not expected_path.exists():
        return "FAIL", [f"FAIL  {label:48} no expectation recorded (run `make record`)"]
    expected = json.loads(expected_path.read_text(encoding="utf-8"))
    if not expected.get("authoritative") and not allow_unpinned:
        return "FAIL", [f"FAIL  {label:48} expectation recorded with {expected['recorded_with']}, not the pin"]
    actual = run_case(cmd, case, header.mask, extra_env)
    diffs = [k for k in ("stdout", "stderr", "exit_code") if actual[k] != expected[k]]
    if not diffs:
        return "PASS", [f"PASS  {label}"]
    lines = [f"FAIL  {label:48} differs in {', '.join(diffs)}"]
    for k in diffs:
        lines += [f"      expected {k}: {expected[k]!r}", f"      actual   {k}: {actual[k]!r}"]
    return "FAIL", lines


def cmd_check(args: argparse.Namespace) -> int:
    cases = iter_cases(args.filter)
    if not cases:
        print("check: no case selected", file=sys.stderr)
        return 2
    failures = 0
    for case in cases:
        header = read_header(case)
        cmd = [part.replace("{case}", case.name) for part in args.runner.split()]
        if header.status == "X":
            trace = run_case(cmd, case)
            ok = trace["exit_code"] != 0 and (header.expect or "") in str(trace["stderr"])
            print(f"{'PASS' if ok else 'FAIL'}  {case.name:48} (must be rejected with {header.expect})")
            failures += not ok
            continue
        if header.status == "P2+":
            trace = run_case(cmd, case)
            stderr = str(trace["stderr"])
            ok = trace["exit_code"] != 0 and P2_MARKER in stderr and (header.expect or "") in stderr
            print(f"{'PASS' if ok else 'FAIL'}  {case.name:48} (must be refused with {P2_MARKER}"
                  f"{' ' + header.expect if header.expect else ''})")
            failures += not ok
            continue
        status, lines = _compare(cmd, case, header, args.allow_unpinned, header.deviation)
        print("\n".join(lines))
        failures += status == "FAIL"
    print(f"\n{len(cases) - failures}/{len(cases)} passed")
    return 1 if failures else 0


def cmd_verify(args: argparse.Namespace) -> int:
    """The oracle checked against itself: the pinned CPython must reproduce every expectation.
    Excluded-construct (X) cases are rejected by the compiler, so CPython has nothing to verify."""
    version = python_version(args.python)
    if version != pinned_python():
        print(f"verify: {args.python} is {version}; the oracle is {pinned_python()}", file=sys.stderr)
        return 2
    cases = [c for c in iter_cases(args.filter) if read_header(c).status != "X"]
    if not cases:
        print("verify: no case selected", file=sys.stderr)
        return 2
    failures = checked = 0
    for case in cases:
        header = read_header(case)
        for deviation in [None] + ([header.deviation] if header.deviation else []):
            status, lines = _compare([args.python, case.name], case, header, allow_unpinned=False,
                                     deviation=deviation, extra_env=simulation_env(deviation, args.python))
            print("\n".join(lines))
            failures += status == "FAIL"
            checked += 1
    print(f"\nverify: {checked - failures}/{checked} expectations reproduced by CPython {version}")
    return 1 if failures else 0


def cmd_list(args: argparse.Namespace) -> int:
    for case in iter_cases(args.filter):
        h = read_header(case)
        print(f"{h.clause:8} {h.status:4} {h.spec:12} {case.name:48} {h.deviation or '':5} {h.source}")
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
    v = sub.add_parser("verify")
    v.add_argument("--python", default=sys.executable)
    v.add_argument("--filter")
    v.set_defaults(fn=cmd_verify)
    ls = sub.add_parser("list")
    ls.add_argument("--filter")
    ls.set_defaults(fn=cmd_list)
    args = ap.parse_args(argv)
    return int(args.fn(args))


if __name__ == "__main__":
    raise SystemExit(main())
