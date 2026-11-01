# clause: C-2-02
# spec: section 2
# status: P1
# source: TODO task 2 (chained-comparison short-circuit with rich comparisons); spec section 3
"""a < b < c evaluates b once, left to right; it stops at the first comparison whose result is
false, taking that result's truth exactly once, and the value of the chain is that result
object, or the last one, not a bool."""
log: list[str] = []


class Verdict:
    def __init__(self, label: str, truth: bool) -> None:
        self.label = label
        self.truth = truth

    def __bool__(self) -> bool:
        log.append(f"bool {self.label}")
        return self.truth

    def __repr__(self) -> str:
        return f"Verdict({self.label})"


class R:
    def __init__(self, name: str, rank: int) -> None:
        self.name = name
        self.rank = rank

    def __lt__(self, other: R) -> Verdict:
        log.append(f"{self.name}<{other.name}")
        return Verdict(f"{self.name}<{other.name}", self.rank < other.rank)


def make(name: str, rank: int) -> R:
    log.append(f"make {name}")
    return R(name, rank)


result = make("a", 1) < make("b", 2) < make("c", 3)
print(result, log)
log.clear()
result = make("a", 2) < make("b", 1) < make("c", 3)
print(result, log)
log.clear()
print("in an if:", "yes" if make("a", 1) < make("b", 2) < make("c", 0) else "no", log)
