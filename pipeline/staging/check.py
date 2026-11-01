#!/usr/bin/env python3
"""`make staging-check`: the staging prototype's evidence (docs/staging.md), in one run.

1. The dry run is deterministic: the standard library's artefact and the staging cases' are
   byte-identical under PYTHONHASHSEED 0 and 1.
2. Every [P1] conformance case prints CPython's trace under the replay (no exec but staged
   code, the annotationlib shim over the generated entry points, the phase-1 omissions); the
   [P2+] cases the replay can refuse are refused, by the refusal itself (exit status 70 and the
   `bella: refused: [P2+]` line), not by any failure.
3. The phase-1 targets agree with their recordings under the replay, with each mechanism.
4. The comparison of the two mechanisms over the standard library's phase-1 closure.
Exit status 1 if any of 1 to 3 fails; 4 is a report.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from pipeline.staging import run  # noqa: E402

PY = sys.executable
RUN = str(run.HERE / "run.py")
CASES = run.REPO / "conformance" / "cases"
STAGING_CASES = ["C-8-08_staged_dataclass.py", "C-8-09_staged_namedtuple.py", "C-3-21_annotate_formats.py",
                 "C-3-22_forwardref_unbound_name.py"]
REFUSED_CASES = {"C-3-23_forwardref_evaluate_expression.py": "ForwardRef", "C-3-24_signatures_at_runtime.py": "signature",
                 "C-7-16_gettext_plural_forms.py": "Plural-Forms"}


def deterministic(blocked: list[str]) -> list[str]:
    problems = []
    with tempfile.TemporaryDirectory() as tmp:
        jobs = [("stdlib", ["--modules-from", str(run.LOCK), "--tables", "all", "--shims", str(run.SHIMS)])]
        jobs += [(case, ["--entry", str(CASES / case)]) for case in STAGING_CASES]
        for label, args in jobs:
            outs = []
            for seed in ("0", "1"):
                out = Path(tmp, f"{label}-{seed}")
                run.dry_run(out, blocked, args, seed=seed)
                outs.append(out.with_suffix(".json").read_bytes())
            print(f"{'ok  ' if outs[0] == outs[1] else 'FAIL'} dry run of {label} under hash seeds 0 and 1")
            if outs[0] != outs[1]:
                problems.append(f"the dry run of {label} depends on the hash seed")
    return problems


def judge_corpus(proc: subprocess.CompletedProcess[str]) -> list[str]:
    """The harness run's verdict: a FAIL line, a non-zero exit or no summary line all fail the
    gate, with the harness's stderr kept (review 2026-11-01 astra-low-05, A5-4)."""
    lines = proc.stdout.strip().splitlines()
    failed = [line for line in lines if line.startswith("FAIL")]
    summary = lines[-1] if lines and lines[-1].endswith("passed") else None
    print(summary or "no summary from the harness", "(P1 cases under the replay)")
    for line in failed:
        print("   ", line[:160])
    if proc.returncode != 0 and not failed:
        failed.append(f"the harness exited with status {proc.returncode}: {proc.stderr.strip()[-400:]}")
    if summary is None and not failed:
        failed.append(f"the harness printed no summary: {proc.stderr.strip()[-400:]}")
    return failed


def corpus() -> list[str]:
    harness = str(run.REPO / "conformance" / "harness.py")
    proc = subprocess.run([PY, harness, "check", "--status", "P1", "--runner", f"{PY} {RUN} {{case}}"],
                          capture_output=True, text=True, check=False)
    failed = judge_corpus(proc)
    for case, expect in REFUSED_CASES.items():
        p2 = subprocess.run([PY, RUN, case], cwd=CASES, capture_output=True, text=True,
                            env=dict(os.environ, PYTHONHASHSEED="0"), check=False)
        refusal = [line for line in p2.stderr.splitlines() if line.startswith("bella: refused: [P2+]")]
        refused = p2.returncode == 70 and len(refusal) == 1 and expect in refusal[0]
        print(f"{'ok  ' if refused else 'FAIL'} {case} [P2+] refused: {(refusal or [p2.stderr.strip()[-160:]])[0][:150]}")
        if not refused:
            failed.append(f"{case} was not refused as [P2+] (exit {p2.returncode})")
    return failed


def targets() -> list[str]:
    problems = []
    phase1 = [n for n, t in json.loads(subprocess.run(
        [PY, "-c", "import json,tomllib;print(json.dumps(tomllib.load(open('targets/targets.toml','rb'))))"],
        cwd=run.REPO, capture_output=True, text=True, check=True).stdout).items() if t["stage"] != "later"]
    for mechanism in ("staged", "intrinsics"):
        runner = f"{PY} {RUN} --mechanism {mechanism} --program-lock closure/{{name}}.lock.json -P {{driver}} {{argv}}"
        proc = subprocess.run([PY, str(run.REPO / "targets" / "run_targets.py"), "check", "--runner", runner,
                               *(a for n in phase1 for a in ("--target", n))],
                              capture_output=True, text=True, check=False)
        print(f"{'ok  ' if proc.returncode == 0 else 'FAIL'} phase-1 targets under the replay, mechanism {mechanism}: "
              + ", ".join(line.split()[1] for line in proc.stdout.splitlines() if line.startswith("ok")))
        if proc.returncode != 0 and mechanism == "staged":
            problems.append(proc.stdout)
    return problems


def compare(stdlib: Path) -> None:
    a = json.loads(stdlib.with_suffix(".json").read_text(encoding="utf-8"))
    by_site: dict[str, list[dict[str, Any]]] = {}
    for t in a["texts"]:
        by_site.setdefault(str(t["site"]), []).append(t)
    intrinsic_texts = set(a["intrinsics"].values())
    print("\nMechanisms over the standard library's phase-1 closure (closure.lock.json):")
    for site, texts in sorted(by_site.items()):
        covered = sum(1 for t in texts if t["text"] in intrinsic_texts)
        print(f"  {site:52} {len(texts):3} texts staged by the dry run, {covered:3} generated by an intrinsic")
        for t in texts:
            if site.startswith("collections") and t["text"] not in intrinsic_texts:
                print(f"      no intrinsic: {t['text'][:70]}  (from {', '.join(map(str, t['by']))})")
    idle = [s for s in a["exec_sites"] if s["texts"] == 0 and not s["site"].startswith("importlib")]
    print(f"  exec/eval/compile sites in the closure that stage nothing ({len(idle)}): refused if reached at runtime")
    for s in idle:
        print(f"      {s['kind']:7} {s['site']}")
    print(f"  annotate entry points {len(a['annotate_entry_points'])}, declined {len(a['annotate_declined'])}: "
          + "; ".join(d.split("::", 1)[1] for d in a["annotate_declined"]))
    print(f"  inputs read by module bodies: {a['inputs'] or 'none'}")


def main() -> int:
    blocked = run.phase1_blocked()
    stdlib = run.stdlib_artefact(blocked)
    problems = deterministic(blocked) + corpus() + targets()
    compare(stdlib)
    print("\n" + ("staging-check: " + "; ".join(p.strip().splitlines()[0] for p in problems) if problems
                  else "staging-check: all evidence holds"))
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
