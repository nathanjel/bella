#!/usr/bin/env python3
"""Run the phase-0 target programs and compare them with their recorded output.

    python3 targets/run_targets.py record            # under the pinned CPython: writes expected/
    python3 targets/run_targets.py check             # CPython again (determinism, second hash seed)
    python3 targets/run_targets.py check --runner "build/{name} {argv}"   # the compiled binaries
    python3 targets/run_targets.py list

Each target is a driver script plus fixed inputs (`targets.toml`); the observable is stdout,
stderr and the exit status. Recording is authoritative only under the pinned interpreter
(`bella.toml`); elsewhere `--allow-unpinned` records with a non-authoritative marker, as the
conformance harness does. `check` runs every target under PYTHONHASHSEED=1 as well as 0, so a
program whose output depends on hash order fails before the compiler ever sees it, and once more
in the phase-1 configuration (the manifest's omissions and the codecs outside the phase-1 set
blocked, as deviation D-20 is simulated) when the target belongs to phase 1: it must print the
same there, since that is how phase 1 runs it. `check` compares bytes, and only against an authoritative recording made on the
pinned interpreter (`--allow-unpinned` relaxes that for development); each run has a time limit.
"""
from __future__ import annotations

import argparse
import json
import os
import shlex
import subprocess
import sys
import tomllib
from pathlib import Path
from typing import TypedDict

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
EXPECTED = HERE / "expected"


def pinned_python() -> str:
    cfg = tomllib.loads((ROOT / "bella.toml").read_text(encoding="utf-8"))
    return str(cfg["reference"]["python"])


def current_python() -> str:
    v = sys.version_info
    return f"{v.major}.{v.minor}.{v.micro}"


class Target(TypedDict):
    kind: str
    level: str
    stage: str
    driver: str
    argv: list[str]
    packages: list[str]
    stressors: list[str]


def load_targets() -> dict[str, Target]:
    data = tomllib.loads((HERE / "targets.toml").read_text(encoding="utf-8"))
    return {name: Target(kind=t["kind"], level=t["level"], stage=t["stage"], driver=t["driver"], argv=list(t["argv"]),
                         packages=list(t["packages"]), stressors=list(t.get("stressors", []))) for name, t in data.items()}


TIMEOUT = 600   # seconds per run: a hung program, or a hung compiled binary, fails instead of blocking


def env_for(seed: int, phase1: bool = False) -> dict[str, str]:
    env = {k: v for k, v in os.environ.items() if not k.startswith("PYTHON")}
    env.update(PYTHONPATH=str(HERE / "vendor"), PYTHONHASHSEED=str(seed), PYTHONUTF8="1", PYTHONIOENCODING="utf-8",
               PYTHONDONTWRITEBYTECODE="1", LC_ALL="C.UTF-8", TZ="UTC", COLUMNS="80")
    if phase1:   # deviation D-20, as conformance/harness.py simulates it
        sys.path.insert(0, str(ROOT))
        from conformance.harness import _phase1_blocked
        env.update(PYTHONPATH=f"{ROOT / 'conformance' / 'simulate'}{os.pathsep}{HERE / 'vendor'}",
                   BELLA_SIMULATE_BLOCK=",".join(_phase1_blocked(sys.executable)))
    return env


class Result(TypedDict):
    stdout: bytes
    stderr: bytes
    exit: int


def run_one(name: str, spec: Target, runner: str | None, seed: int, phase1: bool = False) -> Result:
    argv = spec["argv"]
    if runner is None:
        cmd = [sys.executable, "-P", spec["driver"], *argv]
    else:
        cmd = shlex.split(runner.format(name=name, driver=spec["driver"], argv=" ".join(shlex.quote(a) for a in argv)))
    try:   # bytes, not decoded text: CRLF and malformed UTF-8 must not pass for something else (A4 note)
        proc = subprocess.run(cmd, cwd=HERE, env=env_for(seed, phase1), capture_output=True, timeout=TIMEOUT)
    except subprocess.TimeoutExpired as exc:
        return Result(stdout=exc.stdout or b"", stderr=(exc.stderr or b"") + f"<timeout after {TIMEOUT} s>".encode(), exit=-1)
    return Result(stdout=proc.stdout, stderr=proc.stderr, exit=proc.returncode)


def record(args: argparse.Namespace) -> int:
    pinned, current = pinned_python(), current_python()
    authoritative = pinned == current
    if not authoritative and not args.allow_unpinned:
        print(f"refusing to record on CPython {current}: the reference is {pinned} (use --allow-unpinned for a development run)")
        return 2
    EXPECTED.mkdir(exist_ok=True)
    for name, spec in selected(args):
        r = run_one(name, spec, None, 0)
        (EXPECTED / f"{name}.out").write_bytes(r["stdout"])
        (EXPECTED / f"{name}.err").write_bytes(r["stderr"])
        (EXPECTED / f"{name}.json").write_text(json.dumps({"exit": r["exit"], "python": current, "authoritative": authoritative}, indent=1) + "\n", encoding="utf-8")
        print(f"recorded {name}: exit {r['exit']}, {len(r['stdout'].splitlines())} lines{'' if authoritative else '  [NON-AUTHORITATIVE]'}")
    return 0


def selected(args: argparse.Namespace) -> list[tuple[str, Target]]:
    targets = load_targets()
    names = getattr(args, "target", None) or list(targets)
    unknown = [n for n in names if n not in targets]
    if unknown:
        raise SystemExit(f"unknown target(s): {', '.join(unknown)}")
    return [(n, targets[n]) for n in names]


def check(args: argparse.Namespace) -> int:
    failures = 0
    pinned = pinned_python()
    for name, spec in selected(args):
        # CPython: two hash seeds, then the phase-1 configuration for a phase-1 target; a compiled runner: once
        runs = [(0, False)] if args.runner else [(0, False), (1, False)] + ([(0, True)] if spec["stage"] != "later" else [])
        meta = json.loads((EXPECTED / f"{name}.json").read_text(encoding="utf-8"))
        if not (meta.get("authoritative") is True and meta.get("python") == pinned) and not args.allow_unpinned:
            # the oracle must be the reference interpreter's own recording (review 2026-11-01, A4-4)
            failures += 1
            print(f"FAIL {name}: the recording is not authoritative for CPython {pinned} "
                  f"(python {meta.get('python')!r}, authoritative {meta.get('authoritative')!r}); run `make targets-record`")
            continue
        want_out = (EXPECTED / f"{name}.out").read_bytes()
        want_err = (EXPECTED / f"{name}.err").read_bytes()
        for seed, phase1 in runs:
            r = run_one(name, spec, args.runner, seed, phase1)
            problems = []
            if r["stdout"] != want_out:
                problems.append("stdout")
            if r["stderr"] != want_err:
                problems.append("stderr")
            if r["exit"] != meta["exit"]:
                problems.append(f"exit {r['exit']} != {meta['exit']}")
            tag = f"{name} (seed {seed}{', phase-1 omissions' if phase1 else ''})"
            if problems:
                failures += 1
                print(f"FAIL {tag}: {', '.join(problems)}")
                if args.verbose:
                    for label, want, got in (("stdout", want_out, r["stdout"]), ("stderr", want_err, r["stderr"])):
                        for line in _diff(want, got, label)[:20]:
                            print("   " + line)
            else:
                print(f"ok   {tag}")
    print(f"{failures} failure(s)" if failures else "all targets agree with the recording")
    return 1 if failures else 0


def _diff(a: bytes, b: bytes, label: str = "stdout") -> list[str]:
    import difflib

    return list(difflib.unified_diff(a.decode("utf-8", "replace").splitlines(keepends=True),
                                     b.decode("utf-8", "replace").splitlines(keepends=True),
                                     f"expected {label}", f"actual {label}", lineterm=""))


def list_targets(_: argparse.Namespace) -> int:
    for name, spec in load_targets().items():
        pk = ", ".join(spec["packages"]) or "stdlib only"
        print(f"{name:26s} {spec['kind']:8s} {spec['level']:7s} {spec['stage']:6s} {spec['driver']}  [{pk}]")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("record")
    r.add_argument("--allow-unpinned", action="store_true")
    r.add_argument("--target", action="append", help="only this target (repeatable)")
    r.set_defaults(fn=record)
    c = sub.add_parser("check")
    c.add_argument("--runner", help="command template with {name}, {driver}, {argv}; default: this CPython")
    c.add_argument("--allow-unpinned", action="store_true", help="accept a non-authoritative recording (development)")
    c.add_argument("--target", action="append", help="only this target (repeatable)")
    c.add_argument("-v", "--verbose", action="store_true")
    c.set_defaults(fn=check)
    sub.add_parser("list").set_defaults(fn=list_targets)
    args = ap.parse_args(argv)
    return int(args.fn(args))


if __name__ == "__main__":
    raise SystemExit(main())
