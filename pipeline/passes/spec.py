"""PassSpec: every pass is registered with its levels, facts, obligations and proof status.

The pass manager refuses to run a pass whose record is incomplete, and derives the pass order
from the facts (design document, section 8). The proof ladder (section 9) is recorded in
``status``: stated -> tested -> validated -> proved.
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from typing import Any


class Level(Enum):
    L0 = "L0 CPython ast"
    L1 = "L1 PyCore"
    L2 = "L2 Typed IR"
    L3 = "L3 Ownership IR"
    L4 = "L4 C++ intent IR"


class Fact(Enum):
    NO_CHAINED_COMPARE = "no chained comparisons"
    NO_WITH = "no with statements"
    NO_COMPREHENSIONS = "no comprehensions"
    NO_FSTRINGS = "no f-strings"
    NO_DECORATORS = "no decorators"
    CLASS_BODIES_EXPLICIT = "class bodies carry their implicit stores; zero-argument super() is explicit; qualnames recorded"
    PRIVATE_NAMES_MANGLED = "private names mangled"
    NO_IMPORTS = "import statements are intrinsic calls and stores"
    SINGLE_TARGETS = "every assignment has one target"
    NO_MATCH = "no match statements"
    ANNOTATIONS_EXPLICIT = "module and class annotations are __annotate__ functions; module docstrings are __doc__ stores"
    NO_TYPE_PARAMS = "PEP 695 type parameters and aliases are generic scopes and intrinsic calls"
    FUNCTION_ANNOTATIONS_EXPLICIT = "a function's annotations are its __annotate__ function, defined before it"
    EXPLICIT_TRUTH = "truth tests explicit"
    NAMES_BOUND = "every bare name statically bound"
    NAMES_RESOLVED = "every name access is one of CPython's instructions; code objects carry CPython's slot tables"
    ANF = "A-normal form: every operand a constant or a temporary, every operation named, in evaluation order"
    LIFETIMES_EXPLICIT = "every reference a temporary holds ends at a Release or a consumer, where CPython drops it"
    TYPES = "expression types from the oracle"
    RANGES = "integer ranges"
    ESCAPE = "escape and ownership"
    CYCLE_FREEDOM = "cycle-free classes"


class Discharge(Enum):
    TESTED = "rung 1: executable semantics + differential tests"
    VALIDATED = "rung 2: translation validation (Z3 certificate per build)"
    CHECKED = "rung 3: verified checker of an emitted witness"
    PROVED = "rung 4: mechanised proof"


@dataclass(frozen=True)
class Obligation:
    kind: str          # wf | semantics | fact_sound | terminates
    statement: str


@dataclass(frozen=True)
class PassSpec:
    name: str
    source: Level
    target: Level
    requires: frozenset[Fact] = frozenset()
    produces: frozenset[Fact] = frozenset()
    invalidates: frozenset[Fact] = frozenset()
    obligations: tuple[Obligation, ...] = ()
    discharge: Discharge = Discharge.TESTED
    status: str = "stated"          # stated | tested | validated | proved

    def complete(self) -> list[str]:
        """Reasons the record is incomplete (empty means runnable)."""
        problems = []
        if not self.obligations:
            problems.append("no obligations stated")
        kinds = {o.kind for o in self.obligations}
        if "wf" not in kinds:
            problems.append("no well-formedness obligation")
        if "semantics" not in kinds and self.source != self.target:
            problems.append("a lowering pass needs a semantics-preservation obligation")
        if self.status not in ("stated", "tested", "validated", "proved"):
            problems.append(f"unknown status {self.status}")
        return problems


@dataclass
class RegisteredPass:
    spec: PassSpec
    run: Callable[[Any], Any]


REGISTRY: dict[str, RegisteredPass] = {}


def register(spec: PassSpec) -> Callable[[Callable[[Any], Any]], Callable[[Any], Any]]:
    def deco(fn: Callable[[Any], Any]) -> Callable[[Any], Any]:
        if spec.name in REGISTRY:
            raise ValueError(f"pass {spec.name!r} registered twice")
        REGISTRY[spec.name] = RegisteredPass(spec, fn)
        return fn
    return deco


def ladder() -> list[tuple[str, str, str]]:
    """(name, status, discharge) for every registered pass: the proof debt made visible."""
    return [(p.spec.name, p.spec.status, p.spec.discharge.value) for p in REGISTRY.values()]
