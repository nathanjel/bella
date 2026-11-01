# clause: C-3-24
# spec: section 3
# status: P2+
# expect: signature
# source: decision S-2 (2026-11-01, docs/staging.md): function signatures at runtime stay [P2+]
"""inspect.signature of a compiled function, and so the docstring dataclasses generates for a
class without one, read the function's metadata at runtime (docs/targets.md section 5, item 1),
which phase 1 does not have. Phase 1 refuses with the milestone's name."""
import dataclasses
import inspect


@dataclasses.dataclass
class Item:
    name: str
    qty: int = 1


def scale(x: int, factor: float = 2.0, *, exact: bool = False) -> float:
    return x * factor


print(Item.__doc__)
print(inspect.signature(scale))
