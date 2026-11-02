"""The prelude (runtime/prelude/*.py) run by CPython against the builtins it stands for.

The prelude is Python that Bella compiles into every program (docs/DECISIONS.md, step 3 of the
C++ leg). Run by CPython itself, each function must do what the builtin does, observed through
what it calls: the exact sequence of write() and flush() calls on a file object, the values it
str()s, and the exceptions (type and message) it raises, in the same order of checks.

Run under pytest or directly: python3 runtime/tests/test_prelude.py
"""
from __future__ import annotations

import builtins
import contextlib
import importlib.util
import io
import sys
from pathlib import Path
from typing import Any

PRELUDE = Path(__file__).resolve().parents[1] / "prelude"


def load(name: str) -> Any:
    spec = importlib.util.spec_from_file_location(f"bella_prelude_{name}", PRELUDE / f"{name}.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class Recorder:
    """A file object that records every call print makes on it."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, object]] = []

    def write(self, s: object) -> int:
        self.calls.append(("write", s))
        return len(s) if isinstance(s, str) else 0

    def flush(self) -> None:
        self.calls.append(("flush", None))


class Loud:
    """str() of it is observable: it records the call."""

    def __init__(self, log: list[str], name: str) -> None:
        self.log, self.name = log, name

    def __str__(self) -> str:
        self.log.append(self.name)
        return f"<{self.name}>"


class Text(str):
    def __str__(self) -> str:
        return "subclass str()"


def outcome(fn: Any, *args: object, **kwargs: object) -> tuple[object, ...]:
    rec = Recorder()
    log: list[str] = []
    args = tuple(Loud(log, a[1:]) if isinstance(a, str) and a.startswith("@") else a for a in args)
    if kwargs.get("file") == "rec":
        kwargs["file"] = rec
    try:
        with contextlib.redirect_stdout(io.StringIO()) as out:
            result = fn(*args, **kwargs)
        return ("ok", result, rec.calls, log, out.getvalue())
    except Exception as exc:  # noqa: BLE001 -- the exception is the observable
        return ("raised", type(exc).__name__, str(exc), rec.calls, log)


def test_print_matches_the_builtin() -> None:
    prelude = load("builtins")
    cases: list[tuple[tuple[object, ...], dict[str, object]]] = [
        ((), {}),
        ((1, "a", None, True), {}),
        ((1, 2), {"sep": "-", "end": "!"}),
        ((1, 2), {"sep": None, "end": None}),
        (("@x", "@y"), {"file": "rec"}),
        (("@x", "@y"), {"file": "rec", "sep": Text(","), "end": Text(";")}),
        ((1,), {"file": "rec", "flush": True}),
        ((1,), {"file": "rec", "flush": 0}),
        (("@x",), {"sep": 5}),
        (("@x",), {"end": b"x"}),
        (("@x",), {"sep": 5, "end": 5}),
        (("@x",), {"file": "rec", "sep": 1.5}),
    ]
    for args, kwargs in cases:
        want = outcome(builtins.print, *args, **dict(kwargs))
        got = outcome(prelude.print, *args, **dict(kwargs))
        assert got == want, f"print(*{args}, **{kwargs}):\n  prelude {got}\n  builtin {want}"


def test_print_does_nothing_without_a_stdout() -> None:
    prelude = load("builtins")
    saved = sys.stdout
    try:
        sys.stdout = None  # type: ignore[assignment]
        builtins.print("x", sep=5)          # file is resolved first: no TypeError
        prelude.print("x", sep=5)
    finally:
        sys.stdout = saved


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)
