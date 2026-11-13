#!/usr/bin/env python3
"""The names CPython has and the runtime lacks: a list kept under version control, so that what stops by name is known and a
name that goes missing is noticed.

    python tools/missing_names.py            check: what one compiled program finds missing is conformance/names-baseline.txt
    python tools/missing_names.py --update   write the baseline from this run

The names table (runtime/src/cpython_names.inc, tools/cpython_names.py) lists every name of CPython's built-in modules and of
each built-in type. A compiled program that reads one of them the runtime does not have stops by name. This tool compiles one
program that imports every native module of the manifest (mapped and core) and prints each module's own names and the own names
of every type it can reach from them, from builtins, sys and types, and from a sample of objects; what the table has beyond
that is the list. A line is `scope:name`, the scope a module's name or a type's tp_name as the table has it; `?:module.Name` is
a type the table has no scope for.

The list is not a to-do list as it stands: much of it is the dialect's own (frames and code objects, E-02; memoryview and the
asynchronous types, [P2+]; the sys surface of section 7). It says what the runtime answers, not what it should.
"""
from __future__ import annotations

import ast
import os
import re
import subprocess
import sys
import tempfile
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

BASELINE = ROOT / "conformance" / "names-baseline.txt"
# modules of the manifest no program imports (they stop by name at the import), and the two whose namespace is not listed (RL-419)
NOT_IMPORTED = {"_math_integer", "marshal", "zipimport", "_frozen_importlib", "_frozen_importlib_external", "importlib._bootstrap",
                "importlib._bootstrap_external"}

PROGRAM = '''
import builtins, sys, types
{imports}
MODULES = [builtins, sys, {modules}]
seen = set()
def show(t):
    if t in seen:
        return
    seen.add(t)
    print("type", t.__module__, t.__qualname__, t.__name__, sorted(vars(t)))
def reach(value):
    for t in (value if isinstance(value, type) else type(value)).__mro__:
        show(t)
for m in MODULES:
    print("module", m.__name__, sorted(vars(m)))
for m in [*MODULES, types]:
    for value in list(vars(m).values()):
        reach(value)
def function():
    yield
class Old:
    def __getitem__(self, index):
        raise IndexError
for sample in ([], (), {{}}, set(), frozenset(), "", b"", bytearray(), 1, 1.0, 1j, True, None, NotImplemented, ..., range(1), slice(1), iter([]), iter(()),
               iter(""), iter("\u017c"), iter({{}}), {{}}.keys(), {{}}.values(), {{}}.items(), iter({{}}.values()), iter({{}}.items()), iter(set()), iter(range(1)),
               iter(range(2 ** 70, 2 ** 70 + 1)), iter(b""), iter(bytearray()), iter(Old()), iter(list, 0), reversed([]), reversed({{}}), reversed({{}}.values()),
               reversed({{}}.items()), reversed(Old.__mro__), enumerate([]), zip(), map(len, []), filter(None, []), function(), function, len, [].append,
               list.append, list.__add__, [].__add__, dict.fromkeys, type.__dict__["__dict__"], sys.stdout, sys.version_info, sys.flags, sys.float_info,
               sys.int_info, sys.hash_info, sys.implementation, function.__code__, type.__dict__, property(), staticmethod(len), classmethod(len),
               super(type, type), BaseException(), (lambda: sample).__closure__):  # noqa: F821
    reach(sample)
'''


def table() -> dict[str, set[str]]:
    """The names table's rows by scope."""
    text = (ROOT / "runtime" / "src" / "cpython_names.inc").read_text(encoding="utf-8")
    text = text[text.index("CPYTHON_NAMES[] = {"):]
    text = text[:text.index("\n};")]
    scopes: dict[str, set[str]] = {}
    for key in re.findall(r'\{"([^"]+)", "[^"]*"\}', text):
        scope, _, name = key.partition(":")
        scopes.setdefault(scope, set()).add(name)
    return scopes


def measure() -> list[str]:
    """What the table has and one compiled program does not find, sorted."""
    from pipeline.build import build
    manifest = tomllib.loads((ROOT / "manifest.toml").read_text(encoding="utf-8"))["phase1"]
    modules = [m for m in manifest["mapped"] + manifest["core"] if m not in NOT_IMPORTED and m not in ("builtins", "sys")]
    scopes = table()
    with tempfile.TemporaryDirectory() as tmp:
        prog = Path(tmp, "prog.py")
        prog.write_text(PROGRAM.format(imports="\n".join("import " + m for m in modules), modules=", ".join(modules)), encoding="utf-8")
        got = subprocess.run([str(build(prog, "prog.py"))], capture_output=True, text=True, check=False, env=dict(os.environ, PYTHONHASHSEED="0"), cwd=tmp)
    if got.returncode != 0:
        raise SystemExit(f"missing_names: the program ended with {got.returncode}: {got.stderr.strip()[-600:]}")
    missing: set[str] = set()
    for line in got.stdout.splitlines():
        kind, rest = line.split(" ", 1)
        if kind == "module":
            name, names = rest.split(" ", 1)
            missing |= {f"{name}:{n}" for n in scopes.get(name, set()) - set(ast.literal_eval(names))}
            continue
        module, qualname, short, names = rest.split(" ", 3)
        dotted = f"{module}.{qualname}"
        scope = next((k for k in ((short, dotted) if module == "builtins" else (dotted, qualname, short)) if k in scopes), None)
        if scope is None:
            missing.add(f"?:{dotted}")
        else:
            missing |= {f"{scope}:{n}" for n in scopes[scope] - set(ast.literal_eval(names))}
    return sorted(missing)


def main() -> int:
    found = measure()
    if "--update" in sys.argv[1:]:
        BASELINE.write_text("\n".join(found) + "\n", encoding="utf-8")
        print(f"missing-names: {len(found)} names written to {BASELINE.relative_to(ROOT)}")
        return 0
    listed = BASELINE.read_text(encoding="utf-8").split()
    gone = sorted(set(found) - set(listed))
    back = sorted(set(listed) - set(found))
    for name in gone:
        print(f"MISSING NOW  {name}")
    for name in back:
        print(f"THERE NOW    {name}  (python tools/missing_names.py --update)")
    print(f"missing-names: {len(found)} names the runtime lacks; baseline {len(listed)}")
    return 1 if gone or back else 0


if __name__ == "__main__":
    sys.exit(main())
