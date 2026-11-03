"""PEP 562: a module's __getattr__ and __dir__ (C-8-10)."""


def __getattr__(name: str) -> int:
    if name == "computed":
        return 42
    raise AttributeError("hooks has no " + name)


def __dir__() -> list[str]:
    return ["zeta", "alpha"]


present = 1
