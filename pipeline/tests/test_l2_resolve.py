"""resolve-names against CPython's own code objects.

For every function and class body of the corpus (and a few standard-library modules of the first
target's closure) that CPython compiles to a code object of the same qualified name, the slot
tables resolve-names computes must be CPython's: `co_varnames`, `co_cellvars`, `co_freevars`, in
CPython's order. The order matters: a frame releases its locals in reverse slot order.

Three differences are L1's by design and are skipped: comprehensions are functions in L1, while
CPython 3.12+ inlines them into the enclosing function (PEP 709), so their variables and the cells
they capture move between tables; PEP 695 scopes are desugared differently; and the bodies of
`async def` functions are not lowered in phase 1.

Run under pytest or directly: python3 -m pipeline.tests.test_l2_resolve
"""
from __future__ import annotations

import sysconfig
import types
from pathlib import Path

from pipeline.l1.frontend import lower
from pipeline.l1.grammar import Unsupported
from pipeline.l2.resolve import Scope, resolve

ROOT = Path(__file__).resolve().parents[2]
STDLIB = Path(sysconfig.get_paths()["stdlib"])
MODULES = ["argparse.py", "enum.py", "dataclasses.py", "re/_parser.py", "gettext.py", "contextlib.py", "statistics.py"]


def _host(code: types.CodeType, out: dict[str, list[types.CodeType]]) -> dict[str, list[types.CodeType]]:
    out.setdefault(code.co_qualname, []).append(code)
    for c in code.co_consts:
        if isinstance(c, types.CodeType):
            _host(c, out)
    return out


def _ours(s: Scope, out: dict[str, list[Scope]]) -> dict[str, list[Scope]]:
    out.setdefault(s.qualname, []).append(s)
    for c in s.children:
        _ours(c, out)
    return out


def differences(path: Path) -> list[str]:
    src = path.read_text(encoding="utf-8")
    try:
        m = lower(src, str(path))
    except Unsupported:
        return []
    host = _host(compile(src, str(path), "exec", dont_inherit=True), {})
    out = []
    for q, ss in _ours(resolve(m).root, {}).items():
        hs = host.get(q)
        if not hs or len(hs) != 1 or len(ss) != 1 or ss[0].kind == "module":
            continue
        h, s = hs[0], ss[0]
        if q.endswith("__annotate__") or "<generic parameters" in q or "<genexpr>" in q or h.co_flags & 0x380:
            continue                     # annotate (hidden parameter name), PEP 695, async bodies
        ours = (() if s.kind == "class" else tuple(n for n in s.varnames if n not in s.synthetic),
                tuple(n for n in s.cellvars if n not in s.synthetic), s.freevars)
        cpython = (() if s.kind == "class" else h.co_varnames, h.co_cellvars, h.co_freevars)
        if ours == cpython:
            continue
        if any(getattr(c.node, "kind", "") in ("coroutine", "async generator") for c in s.children):
            continue                     # what an unlowered async body captures is unknown
        comps = [c for c in s.children if c.qualname.rsplit(".", 1)[-1].startswith("_comp")]
        if comps and ours[2] == cpython[2]:
            # PEP 709: CPython inlines what L1 makes a function, so the comprehensions' own
            # variables join the function's tables and the cells they capture stay locals
            inner = set().union(*(set(c.order) for c in comps)) - set(s.order)
            if (set(cpython[0]) | set(cpython[1])) - inner == set(ours[0]) | set(ours[1]):
                continue
        out.append(f"{path.name}: {q}\n  ours    {ours}\n  CPython {cpython}")
    return out


def test_slot_tables_are_cpythons() -> None:
    paths = sorted((ROOT / "conformance" / "cases").glob("*.py")) + [STDLIB / m for m in MODULES]
    bad = [d for p in paths for d in differences(p)]
    assert not bad, "\n".join(bad)


if __name__ == "__main__":
    test_slot_tables_are_cpythons()
    print("ok test_slot_tables_are_cpythons")
