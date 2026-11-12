"""The functions an adaptation replaces (manifest.toml [replaced]) and their bodies (runtime/replaced/<module>.py): the
manifest and the files name the same functions, each one CPython's with CPython's signature, and the frontend puts every
body in place (pipeline/l1/frontend.py, replace_functions) and keeps CPython's docstring.

Run under pytest or directly: python3 tools/tests/test_replaced.py
"""
from __future__ import annotations

import ast
import importlib.util
import tomllib
from pathlib import Path

from pipeline.l1.frontend import replace_functions

ROOT = Path(__file__).resolve().parents[2]
REPLACED = ROOT / "runtime" / "replaced"


def defs(body: list[ast.stmt], prefix: str = "") -> dict[str, ast.FunctionDef]:
    out: dict[str, ast.FunctionDef] = {}
    for n in body:
        if isinstance(n, ast.FunctionDef):
            out[prefix + n.name] = n
        elif isinstance(n, ast.ClassDef):
            out |= defs(n.body, prefix + n.name + ".")
    return out


def test_the_manifest_and_the_files_name_the_same_functions() -> None:
    listed = tomllib.loads((ROOT / "manifest.toml").read_text(encoding="utf-8"))["replaced"]
    files = {p.stem: p for p in REPLACED.glob("*.py")}
    assert set(listed) == set(files), (sorted(listed), sorted(files))
    for module, names in listed.items():
        assert set(defs(ast.parse(files[module].read_text(encoding="utf-8")).body)) == set(names), module


def test_every_body_goes_in_with_cpythons_signature_and_docstring() -> None:
    for path in REPLACED.glob("*.py"):
        spec = importlib.util.find_spec(path.stem)
        assert spec is not None and spec.origin is not None, path.stem
        original = ast.parse(Path(spec.origin).read_text(encoding="utf-8"))
        before = {q: (ast.dump(d.args), ast.get_docstring(d)) for q, d in defs(original.body).items()}
        tree = ast.parse(Path(spec.origin).read_text(encoding="utf-8"))
        replace_functions(tree, spec.origin)                # refuses a missing function or another signature
        after = defs(tree.body)
        for q in defs(ast.parse(path.read_text(encoding="utf-8")).body):
            assert (ast.dump(after[q].args), ast.get_docstring(after[q])) == before[q], q
            assert ast.dump(after[q]) != ast.dump(defs(original.body)[q]), f"{q}: the body was not replaced"


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)
