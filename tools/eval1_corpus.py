#!/usr/bin/env python3
"""The conformance corpus under eval1 (Gate 0 task 4): a regression guard while L1 grows.

    python tools/eval1_corpus.py            check: every case of the baseline passes
    python tools/eval1_corpus.py --update   write the baseline from this run
    python tools/eval1_corpus.py --level 2  the same through L2 and eval2 (conformance/eval2-baseline.txt)

Runs `conformance/harness.py check` with pipeline/l1/run.py as the runner (the standard library
the host's, the program's own modules eval1's). The baseline, conformance/eval1-baseline.txt,
lists the cases that pass; a listed case that fails is a regression and fails the check; a case
that passes and is not listed is reported, to be added with --update. --update writes only from
a complete run, one with a result for every case of the corpus: a harness that stopped early
would otherwise become the baseline (review 2026-11-02, A7).
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASELINE = ROOT / "conformance" / "eval1-baseline.txt"
CASES = ROOT / "conformance" / "cases"


def baseline_path(level: int) -> Path:
    return BASELINE if level == 1 else ROOT / "conformance" / f"eval{level}-baseline.txt"


def run(level: int = 1) -> dict[str, bool]:
    runner = f"{sys.executable} {ROOT / 'pipeline' / f'l{level}' / 'run.py'} {{case}}"
    proc = subprocess.run([sys.executable, str(ROOT / "conformance" / "harness.py"), "check", "--runner", runner],
                          capture_output=True, text=True, check=False, cwd=ROOT)
    results: dict[str, bool] = {}
    for line in proc.stdout.splitlines():
        parts = line.split()
        if len(parts) >= 2 and parts[0] in ("PASS", "FAIL"):
            results[parts[1]] = parts[0] == "PASS"
    if not results:
        raise SystemExit(f"eval1-corpus: the harness reported nothing\n{proc.stdout}\n{proc.stderr}")
    return results


def main(argv: list[str]) -> int:
    level = int(argv[argv.index("--level") + 1]) if "--level" in argv else 1
    BASELINE = baseline_path(level)  # noqa: N806
    results = run(level)
    passing = sorted(name for name, ok in results.items() if ok)
    if "--update" in argv:
        missing = sorted(p.name for p in CASES.glob("*.py") if p.name[0] in "CX" and p.name not in results)  # the harness's cases
        if missing:
            print(f"eval1-corpus: the run is incomplete, no result for {len(missing)} cases "
                  f"({', '.join(missing[:5])}{', ...' if len(missing) > 5 else ''}); the baseline is unchanged")
            return 1
        BASELINE.write_text("".join(f"{name}\n" for name in passing), encoding="utf-8")
        print(f"eval1-corpus: baseline written, {len(passing)} of {len(results)} cases")
        return 0
    baseline = [line.strip() for line in BASELINE.read_text(encoding="utf-8").splitlines() if line.strip()]
    regressed = [name for name in baseline if not results.get(name, False)]
    new = [name for name in passing if name not in baseline]
    for name in regressed:
        print(f"REGRESSED {name}")
    for name in new:
        print(f"NEW PASS  {name}  (python tools/eval1_corpus.py --update)")
    print(f"eval{level}-corpus: {len(passing)} of {len(results)} cases pass under eval{level}; baseline {len(baseline)}")
    return 1 if regressed else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
