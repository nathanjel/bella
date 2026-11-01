"""The harness fails closed and keeps user payloads observable (review 2026-11-01, astra-low-01 #7).

Run under pytest or directly: python3 -m conformance.tests.test_harness
"""
from __future__ import annotations

import argparse

from conformance import harness


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


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)
