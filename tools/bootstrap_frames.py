"""The import system's frames (the author's decision of 2026-11-25, Question 43; case C-8-22).

The runtime runs CPython 3.15.2's own import system text as two preludes (runtime/prelude/bootstrap.py, run as
_frozen_importlib, and bootstrap_external.py, run as _frozen_importlib_external), and a prelude's functions have no frames:
they stand for C. The import system is Python in CPython, so its functions do have frames there, which the running stack
shows (`<frozen importlib._bootstrap>`, `<frozen importlib._bootstrap_external>`, CPython's lines), the recursion limit
counts and a frame object of the module being imported keeps through `f_back`. This tool writes the table that makes them
so: for each function of the two preludes that CPython's Lib/importlib/_bootstrap.py or _bootstrap_external.py defines
under the same qualified name, the file CPython's frame names and, for every line of the function in the prelude, the line
of CPython's text it is. The prelude's text is CPython's but where a line says `bella:` (the closed world), so most lines
are found as they are; a line the closed world rewrote is given the first line of CPython's text it stands for, and a line
whose CPython line that would not find says so itself with a trailing `# cpython: N`.

    python tools/bootstrap_frames.py            write runtime/prelude/bootstrap_frames.json
    python tools/bootstrap_frames.py --check    fail if it is not what the preludes and the pinned CPython give
"""
from __future__ import annotations

import ast
import difflib
import importlib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PRELUDES = {"bootstrap.py": ("_bootstrap.py", "_bootstrap_external.py"),
            "bootstrap_external.py": ("_bootstrap_external.py", "_bootstrap.py")}
TABLE = ROOT / "runtime" / "prelude" / "bootstrap_frames.json"
FILES = {"_bootstrap.py": "<frozen importlib._bootstrap>", "_bootstrap_external.py": "<frozen importlib._bootstrap_external>"}
OVERRIDE = re.compile(r"\s*# cpython: (\d+)\s*$")
VERSION = "3.15.2"


def functions(text: str) -> dict[str, list[tuple[int, int]]]:
    """Every function's qualified name and the lines of each definition under it, from its first decorator's to its last:
    a property's getter and setter are two (review A46, RL-952)."""
    out: dict[str, list[tuple[int, int]]] = {}

    def walk(body: list[ast.stmt], prefix: str) -> None:
        for n in body:
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
                start = min([n.lineno, *(d.lineno for d in n.decorator_list)])
                out.setdefault(prefix + n.name, []).append((start, n.end_lineno or n.lineno))
                walk(n.body, prefix + n.name + ".<locals>.")
            elif isinstance(n, ast.ClassDef):
                walk(n.body, prefix + n.name + ".")
            elif isinstance(n, (ast.If, ast.Try, ast.With, ast.For, ast.While)):
                for field in ("body", "orelse", "finalbody", "handlers"):
                    inner = getattr(n, field, [])
                    walk([s for h in inner for s in (h.body if isinstance(h, ast.ExceptHandler) else [h])], prefix)
    walk(ast.parse(text).body, "")
    return out


def line_map(ours: list[str], first: int, theirs: list[str], their_first: int) -> list[list[int]]:
    """[prelude line, CPython line] for each line of the function: equal lines as they are, a rewritten stretch the first line
    of CPython's it replaces, lines CPython has not the line before them, an override where the prelude gives one."""
    plain = [OVERRIDE.sub("", line).strip() for line in ours]
    sm = difflib.SequenceMatcher(None, plain, [line.strip() for line in theirs], autojunk=False)
    lines: list[list[int]] = []
    for tag, i1, i2, j1, _j2 in sm.get_opcodes():
        for k in range(i1, i2):
            if tag == "equal":
                to = j1 + (k - i1)
            elif tag == "replace":
                to = j1
            else:                                # lines of the prelude's own: the CPython line before them
                to = max(j1 - 1, 0)
            lines.append([first + k, their_first + to])
    for pair in lines:
        if m := OVERRIDE.search(ours[pair[0] - first]):
            pair[1] = int(m.group(1))
    return lines


def table() -> dict[str, object]:
    if ".".join(map(str, sys.version_info[:3])) != VERSION:
        raise SystemExit(f"bootstrap_frames: CPython {VERSION} is the pin; this is {sys.version.split()[0]}")
    lib = Path(importlib.__file__).resolve().parent
    cpython = {name: (lib / name).read_text(encoding="utf-8") for name in FILES}
    theirs = {name: functions(text) for name, text in cpython.items()}
    out: dict[str, object] = {"cpython": VERSION, "preludes": {}}
    for prelude, order in PRELUDES.items():
        text = (ROOT / "runtime" / "prelude" / prelude).read_text(encoding="utf-8")
        ours = text.splitlines()
        rows: dict[str, object] = {}
        for qualname, spans in functions(text).items():
            found = next((f for f in order if qualname in theirs[f]), None)
            if found is None:
                continue                         # the runtime's own: a C function's stand-in, no frame
            lines: list[list[int]] = []
            text_of = cpython[found].splitlines()
            free = list(theirs[found][qualname])
            # each definition beside the one of CPython's its text is closest to: a property's getter and its setter, and
            # of a function CPython defines once for Windows and once for POSIX, the POSIX one the prelude keeps
            for start, end in spans:
                mine = [OVERRIDE.sub("", line).strip() for line in ours[start - 1:end]]
                cstart, cend = max(free, key=lambda span: difflib.SequenceMatcher(
                    None, mine, [line.strip() for line in text_of[span[0] - 1:span[1]]], autojunk=False).ratio())
                free.remove((cstart, cend))
                lines += line_map(ours[start - 1:end], start, text_of[cstart - 1:cend], cstart)
                if not free:
                    break
            rows[qualname] = {"file": FILES[found], "lines": lines}
        out["preludes"][prelude] = rows    # type: ignore[index]
    return out


def main(argv: list[str]) -> int:
    made = json.dumps(table(), indent=None, separators=(",", ":"), sort_keys=True) + "\n"
    if argv[1:] == ["--check"]:
        if not TABLE.exists() or TABLE.read_text(encoding="utf-8") != made:
            print("bootstrap_frames: runtime/prelude/bootstrap_frames.json is not what the preludes and CPython give; "
                  "run python tools/bootstrap_frames.py", file=sys.stderr)
            return 1
        print(f"bootstrap_frames: agree with CPython {VERSION}")
        return 0
    TABLE.write_text(made, encoding="utf-8")
    shown = sum(len(rows) for rows in json.loads(made)["preludes"].values())
    print(f"bootstrap_frames: {shown} functions of the import system have CPython's frames")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
