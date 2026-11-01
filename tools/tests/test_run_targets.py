"""targets/run_targets.py checks only against an authoritative recording on the pin (review
2026-11-01, astra-low-04 A4-4). Each test copies one target's recording to a temporary directory."""
from __future__ import annotations

import argparse
import importlib.util
import json
import shutil
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from types import ModuleType

ROOT = Path(__file__).resolve().parents[2]


def _load() -> ModuleType:
    spec = importlib.util.spec_from_file_location("run_targets", ROOT / "targets" / "run_targets.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@contextmanager
def _recording(meta: dict[str, object] | None) -> Iterator[ModuleType]:
    rt = _load()
    with tempfile.TemporaryDirectory() as tmp:
        for ext in ("out", "err", "json"):
            shutil.copy(rt.EXPECTED / f"cli_easy_slugs.{ext}", Path(tmp, f"cli_easy_slugs.{ext}"))
        if meta is not None:
            Path(tmp, "cli_easy_slugs.json").write_text(json.dumps(meta), encoding="utf-8")
        vars(rt)["EXPECTED"] = Path(tmp)   # point the runner at the copy
        yield rt


def _check(rt: ModuleType, allow_unpinned: bool = False) -> int:
    args = argparse.Namespace(runner=None, verbose=False, allow_unpinned=allow_unpinned, target=["cli_easy_slugs"])
    return int(rt.check(args))


def test_an_authoritative_recording_on_the_pin_passes() -> None:
    with _recording(None) as rt:
        assert _check(rt) == 0


def test_a_development_recording_is_not_an_oracle() -> None:
    with _recording({"exit": 0, "python": "0.0.0", "authoritative": False}) as rt:
        assert _check(rt) == 1
        assert _check(rt, allow_unpinned=True) == 0          # an explicit development comparison


def test_a_recording_for_another_pin_is_not_an_oracle() -> None:
    with _recording({"exit": 0, "python": "3.14.8", "authoritative": True}) as rt:
        assert _check(rt) == 1


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)
