# clause: C-3-19
# spec: section 3
# status: P2+
# source: TODO task 2 (__getattribute__ override); decision 3 (admitted, tier 2, [P2+])
"""A __getattribute__ override sees every attribute access, including methods and __dict__."""
log: list[str] = []


class Logged:
    def __init__(self) -> None:
        self.x = 1

    def __getattribute__(self, name: str) -> object:
        log.append(name)
        return object.__getattribute__(self, name)

    def method(self) -> str:
        return "m"


o = Logged()
log.clear()
print(o.x, o.method(), sorted(vars(o)), log)
