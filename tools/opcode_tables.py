"""The tables of the `_opcode` prelude, from the pinned CPython.

`runtime/prelude/_opcode.py` is Modules/_opcode.c in Python: its predicates and descriptive tables are the compiler's own
(pycore_opcode_metadata.h), so they are read off the pinned interpreter rather than written by hand. This rewrites the section of
the prelude between the two marker lines, committed like the conformance expectations; `--check` fails when the pinned CPython
disagrees (`make verify`); `--allow-unpinned` runs on another Python, for development only.
"""
from __future__ import annotations

import _opcode  # type: ignore[import-not-found]  # the C module has no stub
import argparse
import sys
import tomllib
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]
OUT = PROJECT / "runtime" / "prelude" / "_opcode.py"
BEGIN = "# ---- the tables (tools/opcode_tables.py; the pin's _opcode over every opcode number) --------------------------------------------\n"
END = "# ---- end of the tables ---------------------------------------------------------------------------------------------------------\n"
PREDICATES = ("is_valid", "has_arg", "has_const", "has_name", "has_jump", "has_free", "has_local", "has_exc")
LAST = 511   # IS_VALID_OPCODE is false past the opcode numbers; the C int's range beyond is the prelude's _int


def pinned_python() -> str:
    return str(tomllib.loads((PROJECT / "bella.toml").read_text(encoding="utf-8"))["reference"]["python"])


def render() -> str:
    lines = [BEGIN]
    for name in PREDICATES:
        predicate = getattr(_opcode, name)
        lines.append(f"_{name.upper()} = frozenset({[op for op in range(LAST + 1) if predicate(op)]!r})\n")
    lines.append(f"_INTRINSIC_1 = {_opcode.get_intrinsic1_descs()!r}\n")
    lines.append(f"_INTRINSIC_2 = {_opcode.get_intrinsic2_descs()!r}\n")
    lines.append(f"_NB_OPS = {_opcode.get_nb_ops()!r}\n")
    lines.append(f"_SPECIAL_METHODS = {_opcode.get_special_method_names()!r}\n")
    lines.append(END)
    return "".join(lines)


def spliced(text: str, tables: str) -> str:
    start, end = text.index(BEGIN), text.index(END) + len(END)
    return text[:start] + tables + text[end:]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=(__doc__ or "").split("\n\n")[0])
    ap.add_argument("--check", action="store_true", help="fail if the prelude's tables are not what the pinned CPython gives")
    ap.add_argument("--allow-unpinned", action="store_true", help="development only")
    args = ap.parse_args(argv)
    version = ".".join(map(str, sys.version_info[:3]))
    if not args.allow_unpinned and version != pinned_python():
        print(f"opcode_tables: run on CPython {pinned_python()}, this is {version}", file=sys.stderr)
        return 2
    current = OUT.read_text(encoding="utf-8")
    text = spliced(current, render())
    if args.check:
        if current != text:
            print(f"opcode_tables: {OUT} disagrees with CPython {version}", file=sys.stderr)
            return 1
        print(f"opcode_tables: agree with CPython {version}")
        return 0
    OUT.write_text(text, encoding="utf-8")
    print(f"opcode_tables: wrote the tables of {OUT.name} from CPython {version}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
