#!/usr/bin/env python3
"""service-tricky: a render handler that turns Markdown requests into HTML (mistune, BSD-3).

    render.py REQUESTS.jsonl

A handler `render(request) -> response` with per-request plugin selection (tables, strikethrough,
task lists, footnotes), driven by fixed requests. Tricky because mistune builds its parser
method tables with getattr(self, "parse_" + name) (tier 2 computed names), loads plugins
through importlib.import_module (tier 2 dynamic import inside the closed world), and uses an
ABC metaclass for directives.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import mistune


def render(request: dict[str, object]) -> dict[str, object]:
    plugins = [str(p) for p in request.get("plugins", [])]  # type: ignore[attr-defined]  # a JSON list of names
    try:
        md = mistune.create_markdown(escape=bool(request.get("escape", True)), plugins=plugins)
    except (ImportError, AttributeError, ValueError) as exc:
        return {"status": 400, "error": type(exc).__name__}
    html = md(str(request["source"]))
    return {"status": 200, "html": html, "length": len(html)}


def main(path: str) -> int:
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        request = json.loads(line)
        response = render(request)
        print(json.dumps({"request": request.get("name"), "response": response}, sort_keys=True, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
