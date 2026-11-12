"""The phase-1 shims written from CPython's modules (runtime/shims/<name>.py) differ from the
pinned standard library only where a line says "bella:" (or in the shim's header comment), and
keep each of CPython's lines at its own line number, so that a traceback through a shim has CPython's.

Run under pytest or directly: python3 tools/tests/test_shims.py
"""
from __future__ import annotations

import difflib
import os
from pathlib import Path

SHIMS = Path(__file__).resolve().parents[2] / "runtime" / "shims"
STDLIB = Path(os.path.dirname(os.__file__))


def unmarked_changes(shim: Path) -> list[str]:
    """Each change of the shim against CPython's module whose shim side has no "bella" mark."""
    ours = shim.read_text(encoding="utf-8").splitlines()
    theirs = (STDLIB / shim.name).read_text(encoding="utf-8").splitlines()
    bad = []
    for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(a=theirs, b=ours, autojunk=False).get_opcodes():
        if tag == "equal":
            continue
        changed = ours[j1:j2]
        if not any("bella" in line.lower() for line in changed):
            bad.append(f"{shim.name}:{j1 + 1}: {tag} {theirs[i1:i2]!r} -> {changed!r}")
    return bad


def test_every_shim_change_is_marked() -> None:
    shims = sorted(SHIMS.glob("*.py"))
    assert shims, "no shims"
    for shim in shims:
        assert (STDLIB / shim.name).exists(), f"{shim.name} is not made from a standard-library module"
        assert unmarked_changes(shim) == [], unmarked_changes(shim)


def moved_lines(shim: Path) -> list[str]:
    """Each run of CPython's lines the shim keeps at another line number than CPython's module has them."""
    ours = shim.read_text(encoding="utf-8").splitlines()
    theirs = (STDLIB / shim.name).read_text(encoding="utf-8").splitlines()
    return [f"{shim.name}: CPython's lines {i1 + 1}-{i2} are the shim's {j1 + 1}-{j2}"
            for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(a=theirs, b=ours, autojunk=False).get_opcodes()
            if tag == "equal" and i1 != j1]


def test_every_shim_keeps_cpythons_line_numbers() -> None:
    """A traceback through a shim has CPython's lines: a marked change takes as many lines as it replaces, and what the
    shim adds (its header, its helpers) comes after CPython's last line."""
    for shim in sorted(SHIMS.glob("*.py")):
        assert moved_lines(shim) == [], moved_lines(shim)




def test_the_collections_abc_shim_has_cpythons_namespace_and_types() -> None:
    """Decision P-2: the shim binds the names CPython's module binds, and the four types it
    imports from _types are the objects CPython's probes find."""
    import importlib.util
    import _collections_abc as real
    spec = importlib.util.spec_from_file_location("bella_shim_collections_abc", SHIMS / "_collections_abc.py")
    assert spec is not None and spec.loader is not None
    shim = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(shim)
    assert set(vars(shim)) - {"__file__", "__cached__", "__spec__", "__loader__", "__name__"} == \
        set(vars(real)) - {"__file__", "__cached__", "__spec__", "__loader__", "__name__"}
    for name in ("generator", "coroutine", "async_generator", "framelocalsproxy"):
        assert getattr(shim, name) is getattr(real, name), name


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)
