"""The harness fails closed and keeps user payloads observable (review 2026-11-01, astra-low-01 #7).

Run under pytest or directly: python3 -m conformance.tests.test_harness
"""
from __future__ import annotations

import argparse
import sys
import tempfile
from pathlib import Path

from conformance import harness

HERE = Path(__file__).resolve().parent


def _check(runner: str, filter_: str) -> int:
    return harness.cmd_check(argparse.Namespace(runner=runner, allow_unpinned=False, filter=filter_))


def test_user_supplied_messages_stay_observable() -> None:
    a = "Traceback (most recent call last):\n  File \"/x/c.py\", line 3, in <module>\n    raise ValueError(\"A\")\nValueError: A\n"
    b = a.replace('"A"', '"B"').replace("ValueError: A", "ValueError: B")
    assert harness.mask_stderr(a) != harness.mask_stderr(b)
    # a case that declares the type masks only that type's wording
    assert harness.mask_stderr(a, frozenset({"ValueError"})) == harness.mask_stderr(b, frozenset({"ValueError"}))
    assert harness.mask_stderr(a, frozenset({"KeyError"})) != harness.mask_stderr(b, frozenset({"KeyError"}))
    assert 'File "c.py", line 3' in harness.mask_stderr(a)          # D-06 still applies


def test_check_fails_closed() -> None:
    nothing = argparse.Namespace(runner="false {case}", allow_unpinned=False, filter="no-such-case-anywhere")
    assert harness.cmd_check(nothing) == 2                           # no case selected is an error, not 0/0
    failing = argparse.Namespace(runner="false {case}", allow_unpinned=False, filter="C-2-01")
    assert harness.cmd_check(failing) == 1                           # a runner that fails every case fails


def test_a_p2_case_passes_only_when_refused_with_the_marker() -> None:
    assert _check(f"{sys.executable} {{case}}", "C-3-14") == 1            # CPython runs it: an accidental pass fails
    assert _check(f"{sys.executable} {HERE / 'fake_p2_runner.py'} {{case}}", "C-3-14") == 0
    assert _check("false {case}", "C-3-14") == 1                          # failing without the marker is not enough


def test_a_deviation_case_is_checked_against_the_deviation_trace() -> None:
    assert _check(f"{sys.executable} {{case}}", "C-7-03") == 1            # CPython's own trace is not what Bella owes
    env = harness.simulation_env("D-20", sys.executable)
    runner = f"env PYTHONPATH={env['PYTHONPATH']} BELLA_SIMULATE_BLOCK={env['BELLA_SIMULATE_BLOCK']} {sys.executable} {{case}}"
    assert _check(runner, "C-7-03") == 0


def test_headers_are_validated() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        bad = Path(tmp, "C-0-01_bad.py")
        for header, fragment in (("# status: P3\n", "not one of"), ("# deviation: D-01\n", "cannot be shown on CPython")):
            bad.write_text(header)
            try:
                harness.read_header(bad)
            except ValueError as exc:
                assert fragment in str(exc), exc
            else:
                raise AssertionError(f"{header!r} accepted")


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)
