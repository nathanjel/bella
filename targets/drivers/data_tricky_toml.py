#!/usr/bin/env python3
"""data-tricky: round-trip and transform TOML documents (tomlkit, MIT).

    toml.py pyproject.toml

Parses a TOML file into tomlkit's document model, applies edits (bump a version, sort a table,
append to an array), dumps it back preserving comments and formatting, and re-parses the
result to verify equality. Tricky because tomlkit's items subclass int/str/datetime with a
mixin (stateful multiple inheritance, tier 3), use __slots__ sparingly, and rely on copy,
inspect and dataclasses.
"""
from __future__ import annotations

import sys
from pathlib import Path

import tomlkit


def main(path: str) -> int:
    text = Path(path).read_text(encoding="utf-8")
    doc = tomlkit.parse(text)
    project = doc["project"]
    major, minor, patch = (int(p) for p in str(project["version"]).split("."))
    project["version"] = f"{major}.{minor}.{patch + 1}"
    deps = project["dependencies"]
    deps.append("bella>=0.0.1")
    deps.sort()
    doc["tool"]["bella"] = tomlkit.table()
    doc["tool"]["bella"]["targets"] = ["linux-x86_64", "linux-aarch64"]
    out = tomlkit.dumps(doc)
    again = tomlkit.parse(out)
    print(out)
    print("round-trip stable:", tomlkit.dumps(again) == out)
    print("version:", again["project"]["version"], type(again["project"]["version"]).__name__)
    print("deps:", list(again["project"]["dependencies"]))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
