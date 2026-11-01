"""Pass manager: orders passes by their facts and refuses incomplete records."""
from __future__ import annotations

from typing import Any

from pipeline.passes.spec import REGISTRY, Fact, Level, PassSpec, RegisteredPass


class PassError(Exception):
    pass


def order(passes: list[RegisteredPass], available: frozenset[Fact] = frozenset()) -> list[RegisteredPass]:
    """Topological order: a pass runs once every fact it requires has been produced and not
    invalidated since. Deterministic (registration order breaks ties); raises on cycles."""
    for p in passes:
        problems = p.spec.complete()
        if problems:
            raise PassError(f"pass {p.spec.name!r} has an incomplete specification: {'; '.join(problems)}")
    remaining = list(passes)
    have = set(available)
    ordered: list[RegisteredPass] = []
    while remaining:
        for p in remaining:
            if p.spec.requires <= have:
                ordered.append(p)
                remaining.remove(p)
                have -= p.spec.invalidates
                have |= p.spec.produces
                break
        else:
            names = ", ".join(p.spec.name for p in remaining)
            missing = {p.spec.name: sorted(f.name for f in p.spec.requires - have) for p in remaining}
            raise PassError(f"no runnable pass among [{names}]; missing facts: {missing}")
    return ordered


def run(tree: Any, passes: list[RegisteredPass], available: frozenset[Fact] = frozenset(),
        trace: list[str] | None = None) -> Any:
    for p in order(passes, available):
        tree = p.run(tree)
        if trace is not None:
            trace.append(p.spec.name)
    return tree


def pipeline(names: list[str]) -> list[RegisteredPass]:
    missing = [n for n in names if n not in REGISTRY]
    if missing:
        raise PassError(f"unknown passes: {missing}")
    return [REGISTRY[n] for n in names]


__all__ = ["Fact", "Level", "PassError", "PassSpec", "order", "pipeline", "run"]
