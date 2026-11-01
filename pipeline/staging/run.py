#!/usr/bin/env python3
"""Run a program under the staging prototype's replay model (docs/staging.md).

    python pipeline/staging/run.py [--mechanism staged|intrinsics] [--program-lock LOCK]
                                   [--] [python options] SCRIPT [ARGS ...]

Build, then run, as a compiler and its binary would. Build: the dry run of the standard
library's phase-1 closure (closure.lock.json; cached under build/staging/, rebuilt when an input
changes) and of the program (the script, and the program modules a target's closure lock
lists). Run: the pinned interpreter on SCRIPT, with pipeline/staging/boot/sitecustomize.py
installing the replay (no exec but staged code, the annotationlib shim, the D-20 omissions).

It is a runner for `conformance/harness.py check --runner` and `targets/run_targets.py check
--runner`: arguments, working directory and environment pass through.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
HERE = REPO / "pipeline" / "staging"
BUILD = REPO / "build" / "staging"
LOCK = REPO / "closure.lock.json"
SHIMS = REPO / "runtime" / "shims"
INPUTS = [LOCK, REPO / "manifest.toml", HERE / "dryrun.py", HERE / "annotations.py", HERE / "annotate_rt.py", HERE / "scan.py",
          HERE / "intrinsics.py", *sorted(SHIMS.glob("*.py"))]


def phase1_blocked() -> list[str]:
    """D-20's list, as the conformance harness computes it (cached with the stdlib artefact)."""
    spec = importlib.util.spec_from_file_location("bella_harness", REPO / "conformance" / "harness.py")
    assert spec is not None and spec.loader is not None
    harness = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(harness)
    blocked: list[str] = harness._phase1_blocked(sys.executable)
    return blocked


def _key(paths: list[Path], *extra: str) -> str:
    h = hashlib.sha256(sys.version.encode())
    for p in paths:
        h.update(str(p).encode())
        h.update(p.read_bytes())
    for e in extra:
        h.update(e.encode())
    return h.hexdigest()[:16]


def dry_run(out: Path, blocked: list[str], args: list[str], seed: str | None = None) -> None:
    """One dry run, in the phase-1 configuration (conformance/simulate blocks the omissions)."""
    env = dict(os.environ, BELLA_SIMULATE_BLOCK=",".join(blocked),
               PYTHONPATH=os.pathsep.join(filter(None, [str(REPO / "conformance" / "simulate"),
                                                        os.environ.get("PYTHONPATH", "")])))
    env.pop("BELLA_STAGING", None)
    if seed is not None:
        env["PYTHONHASHSEED"] = seed
    proc = subprocess.run([sys.executable, "-P", str(HERE / "dryrun.py"), "--out", str(out.with_suffix(".json")),
                           "--binary", str(out.with_suffix(".bin")), *args],
                          env=env, capture_output=True, text=True, check=False)
    if proc.returncode != 0:
        sys.stderr.write(proc.stdout + proc.stderr)
        raise SystemExit(f"bella: the dry run failed ({' '.join(args)})")


def current(out: Path) -> bool:
    """A cached artefact is current while every source it was made from is unchanged (review
    2026-11-01 astra-low-05, A5-2): imported program modules count, not only the entry."""
    if not (out.with_suffix(".bin").exists() and out.with_suffix(".json").exists()):
        return False
    sources = json.loads(out.with_suffix(".json").read_text(encoding="utf-8")).get("sources", {})
    for path, digest in sources.items():
        try:
            if hashlib.sha256(Path(path).read_bytes()).hexdigest() != digest:
                return False
        except OSError:
            return False
    return bool(sources)


def stdlib_artefact(blocked: list[str]) -> Path:
    out = BUILD / f"stdlib-{_key(INPUTS, *blocked)}"
    if not current(out):
        BUILD.mkdir(parents=True, exist_ok=True)
        dry_run(out, blocked, ["--modules-from", str(LOCK), "--tables", "all", "--shims", str(SHIMS),
                               "--unsupported-from", str(LOCK)])
    return out


def program_artefact(script: Path, program_lock: Path | None, blocked: list[str], safe_path: bool = False) -> Path:
    modules: list[str] = []
    paths = [script, *INPUTS]
    if program_lock is not None:
        lock = json.loads(program_lock.read_text(encoding="utf-8"))
        root = lock["roots"][0]
        modules = sorted(n for n, m in lock["modules"].items() if m["status"] == "program" and n != root)
        paths.append(program_lock)
    out = BUILD / "programs" / f"{script.stem}-{_key(paths, os.environ.get('PYTHONPATH', ''), str(safe_path), *blocked)}"
    if not current(out):
        out.parent.mkdir(parents=True, exist_ok=True)
        dry_run(out, blocked, ["--entry", str(script), *(a for m in modules for a in ("--program-module", m)),
                               *(["--safe-path"] if safe_path else []),
                               *(["--unsupported-from", str(program_lock)] if program_lock else [])])
    return out


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--mechanism", choices=("staged", "intrinsics"), default="staged")
    ap.add_argument("--program-lock", type=Path, help="a target's closure lock: its program modules are staged too")
    ours, rest = ap.parse_known_args(argv)
    if rest[:1] == ["--"]:
        rest = rest[1:]
    python_options = []
    while rest and rest[0].startswith("-"):
        python_options.append(rest.pop(0))
    if not rest:
        ap.error("no script")
    script = Path(rest[0])
    blocked = phase1_blocked()
    safe_path = any(o == "-P" or (o.startswith("-") and not o.startswith("--") and "P" in o[1:]) for o in python_options)
    artefacts = [stdlib_artefact(blocked), program_artefact(script, ours.program_lock, blocked, safe_path)]
    env = dict(os.environ, BELLA_STAGING="replay", BELLA_SIMULATE_BLOCK=",".join(blocked),
               BELLA_STAGING_ARTEFACTS=os.pathsep.join(str(a.with_suffix(".bin")) for a in artefacts),
               BELLA_STAGING_SHIMS=str(SHIMS), BELLA_STAGING_MECHANISM=ours.mechanism,
               BELLA_STAGING_RT=str(HERE / "annotate_rt.py"),
               PYTHONPATH=os.pathsep.join(filter(None, [str(HERE / "boot"), os.environ.get("PYTHONPATH", "")])))
    sys.stdout.flush()
    os.execve(sys.executable, [sys.executable, *python_options, *rest], env)


if __name__ == "__main__":
    raise SystemExit(main())
