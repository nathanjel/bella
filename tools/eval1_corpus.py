#!/usr/bin/env python3
"""The conformance corpus under eval1 (Gate 0 task 4): a regression guard while L1 grows.

    python tools/eval1_corpus.py            check: every case of the baseline passes
    python tools/eval1_corpus.py --update   write the baseline from this run
    python tools/eval1_corpus.py --level 2  the same through L2 and eval2 (conformance/eval2-baseline.txt)
    python tools/eval1_corpus.py --level c  compiled through L2 into C++ (conformance/evalc-baseline.txt)

Runs `conformance/harness.py check` with pipeline/l1/run.py as the runner (the standard library
the host's, the program's own modules eval1's). The baseline, conformance/eval1-baseline.txt,
lists the cases that pass; a listed case that fails is a regression and fails the check; a case
that passes and is not listed is reported, to be added with --update. --update writes only from
a complete run, one with a result for every case of the corpus: a harness that stopped early
would otherwise become the baseline (review 2026-11-02, A7). The compiled level's baseline is the
exact build's: with BELLA_FIDELITY=lean in the environment the cases are built lean (pipeline/build.py
reads it), the summary says so, and --update is refused.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASELINE = ROOT / "conformance" / "eval1-baseline.txt"
CASES = ROOT / "conformance" / "cases"


def baseline_path(level: int | str) -> Path:
    return BASELINE if level == 1 else ROOT / "conformance" / f"eval{level}-baseline.txt"


def fidelity(level: int | str) -> str:
    """Which build the compiled level runs: pipeline/build.py reads BELLA_FIDELITY when the harness starts it (an empty
    value is none). The evaluators have no such choice."""
    return (os.environ.get("BELLA_FIDELITY") or "exact") if level == "c" else "exact"


def prebuild() -> None:
    """Compile each case before the harness runs it: a closure takes longer than a case's time limit
    the first time, and the units are shared, so one case at a time spends the CPUs on one compiler
    per unit. A case that does not build fails when the harness runs it, with the build's own words."""
    for case in sorted(CASES.glob("*.py")):
        if case.name[0] in "CX":
            subprocess.run([sys.executable, str(ROOT / "pipeline" / "build.py"), case.name], capture_output=True, check=False, cwd=CASES)


def run(level: int | str = 1) -> dict[str, bool]:
    if level == "c":
        prebuild()
    script = ROOT / "pipeline" / "build.py" if level == "c" else ROOT / "pipeline" / f"l{level}" / "run.py"
    runner = f"{sys.executable} {script} {'--run ' if level == 'c' else ''}{{case}}"
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
    given = argv[argv.index("--level") + 1] if "--level" in argv else "1"
    level: int | str = given if given == "c" else int(given)
    BASELINE = baseline_path(level)  # noqa: N806
    which = fidelity(level)
    if which not in ("exact", "lean"):           # pipeline/build.py's FIDELITIES: every case would fail where it is built
        print(f"eval{level}-corpus: BELLA_FIDELITY is {which!r}, and a build is exact or lean; nothing was run")
        return 2
    if which != "exact" and "--update" in argv:  # before the run: a lean build's results are not the baseline's to hold
        print(f"eval{level}-corpus: BELLA_FIDELITY is {which}, and {BASELINE.name} is the exact build's; the baseline is unchanged "
              f"(unset the variable to write it)")
        return 2
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
    said = "" if which == "exact" else f" [{which} build, against the exact build's baseline]"
    print(f"eval{level}-corpus{said}: {len(passing)} of {len(results)} cases pass under eval{level}; baseline {len(baseline)}")
    return 1 if regressed else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
