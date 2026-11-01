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
program whose output depends on hash order fails before the compiler ever sees it.
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
    driver: str
    argv: list[str]
    packages: list[str]
    stressors: list[str]


def load_targets() -> dict[str, Target]:
    data = tomllib.loads((HERE / "targets.toml").read_text(encoding="utf-8"))
    return {name: Target(kind=t["kind"], level=t["level"], driver=t["driver"], argv=list(t["argv"]),
                         packages=list(t["packages"]), stressors=list(t.get("stressors", []))) for name, t in data.items()}


def env_for(seed: int) -> dict[str, str]:
    env = {k: v for k, v in os.environ.items() if not k.startswith("PYTHON")}
    env.update(PYTHONPATH=str(HERE / "vendor"), PYTHONHASHSEED=str(seed), PYTHONUTF8="1", PYTHONIOENCODING="utf-8",
               PYTHONDONTWRITEBYTECODE="1", LC_ALL="C.UTF-8", TZ="UTC", COLUMNS="80")
    return env


class Result(TypedDict):
    stdout: str
    stderr: str
    exit: int


def run_one(name: str, spec: Target, runner: str | None, seed: int) -> Result:
    argv = spec["argv"]
    if runner is None:
        cmd = [sys.executable, "-P", spec["driver"], *argv]
    else:
        cmd = shlex.split(runner.format(name=name, driver=spec["driver"], argv=" ".join(shlex.quote(a) for a in argv)))
    proc = subprocess.run(cmd, cwd=HERE, env=env_for(seed), capture_output=True, text=True, encoding="utf-8", errors="replace")
    return Result(stdout=proc.stdout, stderr=proc.stderr, exit=proc.returncode)


def record(args: argparse.Namespace) -> int:
    pinned, current = pinned_python(), current_python()
    authoritative = pinned == current
    if not authoritative and not args.allow_unpinned:
        print(f"refusing to record on CPython {current}: the reference is {pinned} (use --allow-unpinned for a development run)")
        return 2
    EXPECTED.mkdir(exist_ok=True)
    for name, spec in load_targets().items():
        r = run_one(name, spec, None, 0)
        (EXPECTED / f"{name}.out").write_text(r["stdout"], encoding="utf-8")
        (EXPECTED / f"{name}.err").write_text(r["stderr"], encoding="utf-8")
        (EXPECTED / f"{name}.json").write_text(json.dumps({"exit": r["exit"], "python": current, "authoritative": authoritative}, indent=1) + "\n", encoding="utf-8")
        print(f"recorded {name}: exit {r['exit']}, {len(r['stdout'].splitlines())} lines{'' if authoritative else '  [NON-AUTHORITATIVE]'}")
    return 0


def check(args: argparse.Namespace) -> int:
    failures = 0
    seeds = [0] if args.runner else [0, 1]
    for name, spec in load_targets().items():
        meta = json.loads((EXPECTED / f"{name}.json").read_text(encoding="utf-8"))
        want_out = (EXPECTED / f"{name}.out").read_text(encoding="utf-8")
        want_err = (EXPECTED / f"{name}.err").read_text(encoding="utf-8")
        for seed in seeds:
            r = run_one(name, spec, args.runner, seed)
            problems = []
            if r["stdout"] != want_out:
                problems.append("stdout")
            if r["stderr"] != want_err:
                problems.append("stderr")
            if r["exit"] != meta["exit"]:
                problems.append(f"exit {r['exit']} != {meta['exit']}")
            tag = f"{name} (seed {seed})"
            if problems:
                failures += 1
                print(f"FAIL {tag}: {', '.join(problems)}")
                if args.verbose:
                    for line in _diff(want_out, r["stdout"])[:20]:
                        print("   " + line)
            else:
                print(f"ok   {tag}")
    print(f"{failures} failure(s)" if failures else "all targets agree with the recording")
    return 1 if failures else 0


def _diff(a: str, b: str) -> list[str]:
    import difflib

    return list(difflib.unified_diff(a.splitlines(), b.splitlines(), "expected", "actual", lineterm=""))


def list_targets(_: argparse.Namespace) -> int:
    for name, spec in load_targets().items():
        pk = ", ".join(spec["packages"]) or "stdlib only"
        print(f"{name:26s} {spec['kind']:8s} {spec['level']:7s} {spec['driver']}  [{pk}]")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("record")
    r.add_argument("--allow-unpinned", action="store_true")
    r.set_defaults(fn=record)
    c = sub.add_parser("check")
    c.add_argument("--runner", help="command template with {name}, {driver}, {argv}; default: this CPython")
    c.add_argument("-v", "--verbose", action="store_true")
    c.set_defaults(fn=check)
    sub.add_parser("list").set_defaults(fn=list_targets)
    args = ap.parse_args(argv)
    return int(args.fn(args))


if __name__ == "__main__":
    raise SystemExit(main())
