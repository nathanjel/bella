"""Standard-library-only differential self-check of the reference model against CPython.

    python -I -m refmodel.selftest --iterations 20000 [--seed N]

Runs random attribute-model programs on the model and on real CPython classes with the same
definitions and stops at the first divergence, printing the operation log as a reproducer.
The Hypothesis version in refmodel/tests shrinks failures; this one needs nothing installed.
"""
from __future__ import annotations

import argparse
import random
import sys

from refmodel.objects import ModelError
from refmodel.oracle import Mismatch, World


def run(iterations: int, seed: int, ops_per_world: int = 60) -> tuple[int, int, int, int, int]:
    """Returns (worlds, ops, cache hits, cache misses, deaths compared); raises Mismatch or ModelError."""
    rng = random.Random(seed)
    worlds = ops = hits = misses = deaths = 0
    while ops < iterations:
        world = World()
        worlds += 1
        try:
            for _ in range(ops_per_world):
                world.apply(world.random_op(rng))
                world.sweep()
                ops += 1
        except ModelError as exc:
            raise ModelError(f"{exc}\nlog:\n" + "\n".join(map(repr, world.log))) from None
        hits += sum(s.hits for s in world.sites.values())
        misses += sum(s.misses for s in world.sites.values())
        deaths += world.deaths_compared
    return worlds, ops, hits, misses, deaths


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--iterations", type=int, default=5000)
    ap.add_argument("--seed", type=int, default=20261031)
    args = ap.parse_args(argv)
    try:
        worlds, ops, hits, misses, deaths = run(args.iterations, args.seed)
    except Mismatch as exc:
        print(f"MISMATCH between model and CPython (seed {args.seed}):\n{exc}", file=sys.stderr)
        return 1
    except ModelError as exc:
        print(f"MODEL INVARIANT VIOLATED (seed {args.seed}):\n{exc}", file=sys.stderr)
        return 1
    print(f"refmodel selftest: {ops} operations over {worlds} worlds, seed {args.seed}: model == CPython; "
          f"inline caches: {hits} hits, {misses} misses; {deaths} deaths in CPython's order")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
