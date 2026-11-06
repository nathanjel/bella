"""Staged texts under eval1 (Gate 0 task 4, step B; docs/staging.md).

The staging dry run records every text a module body hands to exec, eval or compile, keyed
by the function that makes the call (`module:qualname`), the operation and the source as given;
the replay model (pipeline/staging/boot/sitecustomize.py) runs the code CPython compiled from
them. eval1 runs the same texts as L1: each is lowered through the frontend before the program
starts (decision P-1: the whole closure is compiled ahead), in the caller's __future__ context,
with the builtins' preprocessing (eval strips leading spaces and tabs; bytes are decoded by
their PEP 263 declaration). At runtime a call finds its text by the replay's key; a text the
dry run did not record, a refused function's call, and the manifest's [unsupported]
functions stop the program, as in the replay.
"""
from __future__ import annotations

import __future__
import io
import marshal
import tokenize
from pathlib import Path
from typing import Any

from pipeline.l1 import grammar as L
from pipeline.l1.frontend import lower
from pipeline.l1.wf import WellFormednessError, check

_FUTURE_MASK = 0x3FE0000
_FEATURES = {name: getattr(__future__, name).compiler_flag for name in __future__.all_feature_names}


def features(flags: int) -> frozenset[str]:
    """The __future__ features a code object's flags carry."""
    return frozenset(name for name, flag in _FEATURES.items() if flags & flag)


def flags_of(names: frozenset[str]) -> int:
    out = 0
    for name in names:
        out |= _FEATURES.get(name, 0)
    return out & _FUTURE_MASK


def source_text(kind: str, source: str | bytes) -> str:
    """What exec, eval or compile compiles: bytes decoded by their declaration (PEP 263), and
    eval's leading spaces and tabs stripped."""
    if isinstance(source, bytes):
        encoding, _ = tokenize.detect_encoding(io.BytesIO(source).readline)
        text = source.decode(encoding)
        if text.startswith("﻿"):
            text = text[1:]
    else:
        text = source
    return text.lstrip(" \t") if kind == "eval" else text


class Staged:
    def __init__(self, artefacts: list[Path]) -> None:
        self.texts: dict[tuple[str, str, str | bytes], tuple[int, L.Module | str]] = {}
        self.compiled: dict[tuple[Any, ...], tuple[Any, ...]] = {}
        self.code_texts: dict[int, tuple[Any, L.Module | str]] = {}     # id(code) -> (code, lowered)
        self.refused: dict[str, str] = {}
        self.unstaged: dict[str, str] = {}
        self.unsupported: dict[str, set[str]] = {}
        for path in artefacts:
            with open(path, "rb") as f:
                data = marshal.load(f)
            for key, (_code, flags) in data["texts"].items():
                site, kind, source = key
                self.texts[key] = (flags, self._lower(kind, source, flags))
            for key, outcome in data["compiled"].items():
                self.compiled[key] = outcome
                if outcome[0] == "code":
                    _site, _, source, _filename, mode, flags, *_ = key
                    self.code_texts[id(outcome[1])] = (outcome[1], self._lower(mode, source, flags))
            self.refused.update(data["refused"])
            self.unstaged.update(data["unstaged"])
            for module, functions in data["unsupported"].items():
                self.unsupported.setdefault(module, set()).update(functions)

    @staticmethod
    def _lower(kind: str, source: str | bytes, flags: int) -> L.Module | str:
        """The text as L1, or why it does not lower (a refusal when it is reached)."""
        try:
            module = lower(source_text(kind, source), "<string>", mode="eval" if kind == "eval" else "exec",
                           inherit_future=features(flags))
            check(module, frozenset({"__file__"}), strict=False)
            return module
        except (L.Unsupported, L.DialectError, SyntaxError, WellFormednessError) as exc:
            return f"{type(exc).__name__}: {exc}"

    def text(self, site: str, kind: str, source: str | bytes, caller_flags: int) -> L.Module:
        if site in self.refused:
            raise L.Refused(self.refused[site])
        entry = self.texts.get((site, kind, source))
        if entry is None:
            raise L.Refused(self.unstaged.get(site) or
                            f"E-01: {kind} at {site} of a text the dry run did not stage (spec section 8)")
        flags, lowered = entry
        if flags != caller_flags:
            raise L.Refused(f"E-01: {kind} at {site}: the caller's __future__ flags differ from the staged code's")
        if isinstance(lowered, str):
            raise L.Refused(f"{kind} at {site}: the staged text does not lower yet: {lowered}")
        return lowered

    def code(self, code: Any, kind: str, site: str) -> L.Module:
        entry = self.code_texts.get(id(code))
        if entry is None or entry[0] is not code:
            raise L.Refused(f"E-01: {kind} of a code object at {site}")
        if isinstance(entry[1], str):
            raise L.Refused(f"{kind} at {site}: the staged text does not lower yet: {entry[1]}")
        return entry[1]
